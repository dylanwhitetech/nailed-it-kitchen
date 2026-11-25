import { SubmissionAvailability } from "../components/SubmissionAvailability";

/** Submission page shell: explains when submissions are paused. The form is added separately. */
export function SubmitPage() {
  return (
    <section className="page">
      <h1>Submit a recipe</h1>
      <SubmissionAvailability>{() => <p>The recipe submission form is coming soon.</p>}</SubmissionAvailability>
    </section>
  );
}
