import React, { useMemo, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { api } from "../services/api";

export default function Deploy() {
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [isDeploying, setIsDeploying] = useState(false);
  const [status, setStatus] = useState<string>("");
  const [isValidating, setIsValidating] = useState(false);
  const [deployError, setDeployError] = useState<string | null>(null);
  const [skipDependencyCheck, setSkipDependencyCheck] = useState(true);
  const [skipSyntaxCheck, setSkipSyntaxCheck] = useState(false);
  const [secretsText, setSecretsText] = useState("");
  const [validationResult, setValidationResult] = useState<{
    passed: boolean;
    errors: string[];
    warnings: string[];
  } | null>(null);

  const secretsError = useMemo(() => {
    if (!secretsText.trim()) return null;
    try {
      const parsed = JSON.parse(secretsText);
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        return "Secrets must be a JSON object.";
      }
      return null;
    } catch (err) {
      return "Secrets must be valid JSON.";
    }
  }, [secretsText]);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return;
    const selected = e.target.files[0];
    setFile(selected);
    setValidationResult(null);
    setIsValidating(true);
    try {
      const result = await api.validateApp(selected);
      setValidationResult(result);
    } finally {
      setIsValidating(false);
    }
  };

  const handleDeploy = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;

    setIsDeploying(true);
    setDeployError(null);
    try {
      if (secretsError) {
        setDeployError(secretsError);
        return;
      }
      await api.deployApp(file, (newStatus) => setStatus(newStatus), {
        skipDependencyCheck,
        skipSyntaxCheck,
        secrets: secretsText.trim() ? secretsText : undefined,
      });
      alert("Deployment successful!");
      navigate("/dashboard");
    } catch (error) {
      console.error("Deployment failed", error);
      setDeployError(error instanceof Error ? error.message : "Deployment failed");
      setStatus("Deployment failed.");
    } finally {
      setIsDeploying(false);
    }
  };

  const buttonDisabled =
    !file || isDeploying || isValidating || !!secretsError || (validationResult !== null && !validationResult.passed);

  return (
    <div style={{ padding: "2rem", maxWidth: "800px", margin: "0 auto" }}>
      <div style={{ marginBottom: "2rem", display: "flex", alignItems: "center", gap: "1rem" }}>
        <Link to="/dashboard" style={{ color: "#4b5563", textDecoration: "none" }}>
          ← Back to Dashboard
        </Link>
        <h1 style={{ margin: 0 }}>Deploy New Application</h1>
      </div>

      <div
        style={{
          backgroundColor: "white",
          padding: "2rem",
          borderRadius: "8px",
          boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
        }}
      >
        <form onSubmit={handleDeploy} style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
          <div>
            <label style={{ display: "block", marginBottom: "0.5rem", fontWeight: "bold" }}>
              Upload Application ZIP (*.zip)
            </label>
            <div
              style={{
                border: "2px dashed #d1d5db",
                padding: "2rem",
                textAlign: "center",
                borderRadius: "8px",
                backgroundColor: "#f9fafb",
              }}
            >
              <input type="file" accept=".zip" onChange={handleFileChange} style={{ display: "block", margin: "0 auto" }} />
              <p style={{ marginTop: "1rem", color: "#6b7280", fontSize: "0.875rem" }}>
                ZIP must contain main.py, config.yaml, requirements.txt and artifact directories at root.
              </p>
            </div>

            {isValidating && (
              <div
                style={{
                  marginTop: "0.75rem",
                  padding: "0.75rem",
                  backgroundColor: "#fefce8",
                  color: "#854d0e",
                  borderRadius: "4px",
                  fontSize: "0.875rem",
                }}
              >
                Validating ZIP with App Validator...
              </div>
            )}

            {validationResult && validationResult.passed && (
              <div
                style={{
                  marginTop: "0.75rem",
                  padding: "0.75rem",
                  backgroundColor: "#f0fdf4",
                  color: "#166534",
                  borderRadius: "4px",
                  fontSize: "0.875rem",
                }}
              >
                Validation passed. Ready to deploy.
              </div>
            )}

            {validationResult && !validationResult.passed && (
              <div
                style={{
                  marginTop: "0.75rem",
                  padding: "0.75rem",
                  backgroundColor: "#fef2f2",
                  color: "#991b1b",
                  borderRadius: "4px",
                  fontSize: "0.875rem",
                }}
              >
                Validation failed. Fix errors before deploying:
                <ul style={{ margin: "0.5rem 0 0 1rem", padding: 0 }}>
                  {validationResult.errors.map((err, i) => (
                    <li key={i}>{err}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          <div>
            <label style={{ display: "block", marginBottom: "0.5rem", fontWeight: "bold" }}>
              Secrets (JSON, optional)
            </label>
            <textarea
              value={secretsText}
              onChange={(event) => setSecretsText(event.target.value)}
              placeholder='{"OPENAI_API_KEY":"sk-..."}'
              style={{ width: "100%", minHeight: "110px", fontFamily: "monospace", padding: "0.75rem", borderRadius: "6px", border: "1px solid #d1d5db" }}
            />
            {secretsError && (
              <div style={{ marginTop: "0.5rem", color: "#b91c1c", fontSize: "0.875rem" }}>
                {secretsError}
              </div>
            )}
            <div style={{ marginTop: "0.5rem", color: "#6b7280", fontSize: "0.85rem" }}>
              Secrets are saved with the uploaded version and injected at run time.
            </div>
          </div>

          {status && (
            <div style={{ padding: "1rem", backgroundColor: "#eff6ff", color: "#1e3a8a", borderRadius: "4px" }}>
              {status}
            </div>
          )}

          {deployError && (
            <div style={{ padding: "1rem", backgroundColor: "#fef2f2", color: "#991b1b", borderRadius: "4px" }}>
              {deployError}
            </div>
          )}

          <button
            type="submit"
            disabled={buttonDisabled}
            style={{
              backgroundColor: buttonDisabled ? "#9ca3af" : "#2563eb",
              color: "white",
              padding: "0.75rem",
              border: "none",
              borderRadius: "4px",
              cursor: buttonDisabled ? "not-allowed" : "pointer",
              fontWeight: "bold",
              fontSize: "1rem",
            }}
          >
            {isDeploying ? "Deploying..." : "Deploy App"}
          </button>
        </form>
        <div style={{ marginTop: "1.5rem", display: "flex", flexDirection: "column", gap: "0.5rem" }}>
          <label style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
            <input
              type="checkbox"
              checked={skipDependencyCheck}
              onChange={(e) => setSkipDependencyCheck(e.target.checked)}
            />
            Skip dependency check (useful when offline)
          </label>
          <label style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
            <input type="checkbox" checked={skipSyntaxCheck} onChange={(e) => setSkipSyntaxCheck(e.target.checked)} />
            Skip syntax check
          </label>
        </div>
      </div>
    </div>
  );
}

