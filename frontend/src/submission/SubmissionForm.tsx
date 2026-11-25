import { type ChangeEvent, useEffect, useId, useRef, useState } from "react";
import { postSubmission, type SubmissionResult } from "../api/submissions";
import { TurnstileWidget } from "../components/TurnstileWidget";
import { PASTE_TEMPLATE, type RecipeDraft, checkDraft, draftFromRecipe, parsePasteTemplate } from "./recipeText";
import "../styles/submit.css";

type CopyState = "idle" | "copied" | "failed";
type SubmissionError = Extract<SubmissionResult, { status: "error" }>;

const fields = [
  { name: "title", label: "Title", multiline: false, hint: "" },
  { name: "source", label: "Source (optional)", multiline: false, hint: "" },
  { name: "ingredients", label: "Ingredients", multiline: true, hint: "One ingredient per line." },
  { name: "instructions", label: "Instructions", multiline: true, hint: "One step per line." },
  { name: "notes", label: "Notes (optional)", multiline: true, hint: "One note per line." },
] as const satisfies readonly { name: keyof RecipeDraft; label: string; multiline: boolean; hint: string }[];

function retryHint(error: SubmissionError): string | null {
  if (error.retryAfterSeconds !== null) {
    const minutes = Math.max(1, Math.ceil(error.retryAfterSeconds / 60));
    return `You can try again in about ${minutes} minute${minutes === 1 ? "" : "s"}.`;
  }
  return error.retryable ? "Your recipe is still here; you can try again in a few minutes." : null;
}

interface SubmissionFormProps {
  /** Public Turnstile site key from the availability response. */
  siteKey: string;
}

/**
 * Copy-paste recipe submission: copy the template, paste it back, review and edit a plain-text
 * preview, confirm and submit. Checks here mirror the server so problems show early, but the
 * server re-validates everything and decides the outcome.
 */
export function SubmissionForm({ siteKey }: SubmissionFormProps) {
  const id = useId();
  const [copyState, setCopyState] = useState<CopyState>("idle");
  const [pasted, setPasted] = useState("");
  const [parseErrors, setParseErrors] = useState<string[]>([]);
  const [draft, setDraft] = useState<RecipeDraft | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [token, setToken] = useState<string | null>(null);
  const [widgetKey, setWidgetKey] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<SubmissionResult | null>(null);
  const inFlight = useRef(false);
  const draftHeading = useRef<HTMLHeadingElement>(null);
  const successHeading = useRef<HTMLHeadingElement>(null);
  const submitted = result?.status === "submitted";

  useEffect(() => {
    if (submitted) successHeading.current?.focus();
  }, [submitted]);

  const copyTemplate = async () => {
    try {
      await navigator.clipboard.writeText(PASTE_TEMPLATE);
      setCopyState("copied");
    } catch (error) {
      console.error("Copying the recipe template failed", error);
      setCopyState("failed");
    }
  };

  const preview = () => {
    const parsed = parsePasteTemplate(pasted);
    if (!parsed.ok) {
      setParseErrors(parsed.errors);
      return;
    }
    setParseErrors([]);
    setDraft(draftFromRecipe(parsed.recipe));
    setResult(null);
    requestAnimationFrame(() => draftHeading.current?.focus());
  };

  const edit = (name: keyof RecipeDraft) => (event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { value } = event.target;
    setDraft((current) => (current ? { ...current, [name]: value } : current));
  };

  const check = draft ? checkDraft(draft) : null;
  const canSubmit = check !== null && check.errors.length === 0 && confirmed && token !== null && !submitting;

  const submit = async () => {
    if (!check || !token || inFlight.current) return;
    inFlight.current = true;
    setSubmitting(true);
    setResult(null);
    try {
      setResult(await postSubmission(check.recipe, token));
    } finally {
      inFlight.current = false;
      setSubmitting(false);
      // Turnstile tokens are single-use: always start a fresh challenge after an attempt.
      setToken(null);
      setWidgetKey((key) => key + 1);
    }
  };

  const startOver = () => {
    setPasted("");
    setDraft(null);
    setConfirmed(false);
    setResult(null);
    setCopyState("idle");
  };

  if (result?.status === "submitted") {
    return (
      <div className="submission-result submission-result--success">
        <h2 ref={successHeading} tabIndex={-1}>
          Recipe submitted
        </h2>
        <p>
          <output>Thank you, your recipe was submitted. A reviewer will check it before it appears on the site.</output>{" "}
          <a href={result.pullRequestUrl} rel="noopener noreferrer" target="_blank">
            View the pull request on GitHub
          </a>
        </p>
        <button type="button" className="submission-button" onClick={startOver}>
          Submit another recipe
        </button>
      </div>
    );
  }

  return (
    <div className="submission">
      <section className="submission-step" aria-labelledby={`${id}-template`}>
        <h2 id={`${id}-template`}>1. Copy the template</h2>
        <p>Fill it in with one recipe in any text editor. Keep the headings; use one line per item and step.</p>
        <pre className="submission-template">{PASTE_TEMPLATE}</pre>
        <button type="button" className="submission-button" onClick={() => void copyTemplate()}>
          Copy template
        </button>{" "}
        <output className="submission-copy-status">
          {copyState === "copied" && "Template copied."}
          {copyState === "failed" && "Copying didn't work. Select the template text and copy it manually."}
        </output>
      </section>

      <section className="submission-step" aria-labelledby={`${id}-paste`}>
        <h2 id={`${id}-paste`}>2. Paste your recipe</h2>
        <label htmlFor={`${id}-pasted`}>Your filled-in recipe</label>
        <textarea
          id={`${id}-pasted`}
          className="submission-input submission-input--paste"
          rows={14}
          value={pasted}
          onChange={(event) => setPasted(event.target.value)}
          spellCheck
        />
        <button type="button" className="submission-button" onClick={preview} disabled={pasted.trim() === ""}>
          Preview recipe
        </button>
        {parseErrors.length > 0 && (
          <div className="submission-problems" role="alert">
            <p>We couldn't read that recipe. Please fix these problems and preview again:</p>
            <ul>
              {parseErrors.map((error) => (
                <li key={error}>{error}</li>
              ))}
            </ul>
          </div>
        )}
      </section>

      {draft && check && (
        <section className="submission-step" aria-labelledby={`${id}-review`}>
          <h2 id={`${id}-review`} ref={draftHeading} tabIndex={-1}>
            3. Review and submit
          </h2>
          <div className="submission-review">
            <fieldset className="submission-fields">
              <legend>Edit the recipe</legend>
              {fields.map((field) => (
                <div className="submission-field" key={field.name}>
                  <label htmlFor={`${id}-${field.name}`}>{field.label}</label>
                  {field.hint && (
                    <span className="submission-hint" id={`${id}-${field.name}-hint`}>
                      {field.hint}
                    </span>
                  )}
                  {field.multiline ? (
                    <textarea
                      id={`${id}-${field.name}`}
                      className="submission-input"
                      rows={6}
                      value={draft[field.name]}
                      onChange={edit(field.name)}
                      aria-describedby={`${id}-${field.name}-hint`}
                    />
                  ) : (
                    <input
                      id={`${id}-${field.name}`}
                      className="submission-input"
                      type="text"
                      value={draft[field.name]}
                      onChange={edit(field.name)}
                    />
                  )}
                </div>
              ))}
            </fieldset>

            <article className="submission-preview" aria-labelledby={`${id}-preview`}>
              <p className="submission-preview__label" id={`${id}-preview`}>
                Preview{check.slug && ` of recipes/${check.slug}.yaml`}
              </p>
              <h3>{check.recipe.title || "Untitled recipe"}</h3>
              {check.recipe.source && <p>Source: {check.recipe.source}</p>}
              <h4>Ingredients</h4>
              <ul>
                {check.recipe.ingredients.map((item, index) => (
                  <li key={index}>{item}</li>
                ))}
              </ul>
              <h4>Instructions</h4>
              <ol>
                {check.recipe.instructions.map((step, index) => (
                  <li key={index}>{step}</li>
                ))}
              </ol>
              {check.recipe.notes && (
                <>
                  <h4>Notes</h4>
                  <ul>
                    {check.recipe.notes.map((note, index) => (
                      <li key={index}>{note}</li>
                    ))}
                  </ul>
                </>
              )}
            </article>
          </div>

          <div className="submission-problems" aria-live="polite">
            {check.errors.length > 0 && (
              <>
                <p>Fix these problems before submitting:</p>
                <ul>
                  {check.errors.map((error) => (
                    <li key={error}>{error}</li>
                  ))}
                </ul>
              </>
            )}
          </div>

          <p className="submission-warning">
            Your recipe will be public: it is published as a pull request on GitHub, where anyone can read it, and a
            reviewer decides whether it is added. Do not include personal details.
          </p>
          <label className="submission-confirm">
            <input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} />I
            understand my recipe will be public and I have the right to share it.
          </label>
          <TurnstileWidget key={widgetKey} siteKey={siteKey} onToken={setToken} />
          {token === null && <p className="submission-hint">Complete the security check to submit.</p>}
          <button
            type="button"
            className="submission-button submission-button--primary"
            onClick={() => void submit()}
            disabled={!canSubmit}
            aria-busy={submitting}
          >
            {submitting ? "Submitting…" : "Submit recipe"}
          </button>
          {result?.status === "error" && (
            <div className="submission-result submission-result--error" role="alert">
              <p>{result.message}</p>
              {result.errors.length > 0 && (
                <ul>
                  {result.errors.map((error) => (
                    <li key={error}>{error}</li>
                  ))}
                </ul>
              )}
              {retryHint(result) && <p>{retryHint(result)}</p>}
            </div>
          )}
        </section>
      )}
    </div>
  );
}
