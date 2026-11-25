import { SubmissionAvailability } from "../components/SubmissionAvailability";
import { SubmissionForm } from "../submission/SubmissionForm";

/** Recipe submission page: shows the paste-preview-submit form only while submissions are open. */
export function SubmitPage() {
  return (
    <section className="page">
      <h1>Submit a recipe</h1>
      <SubmissionAvailability>{(siteKey) => <SubmissionForm siteKey={siteKey} />}</SubmissionAvailability>
    </section>
  );
}