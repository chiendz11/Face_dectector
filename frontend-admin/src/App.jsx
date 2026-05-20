import Dashboard from "./pages/Dashboard";
import EnrollmentSessionPage from "./features/enrollment/EnrollmentSessionPage";

function getEnrollmentSessionToken() {
  const match = window.location.hash.match(/^#\/enroll\/session\/([^/?#]+)/);
  return match ? decodeURIComponent(match[1]) : "";
}

export default function App() {
  const enrollmentToken = getEnrollmentSessionToken();
  if (enrollmentToken) {
    return <EnrollmentSessionPage token={enrollmentToken} />;
  }

  return <Dashboard />;
}
