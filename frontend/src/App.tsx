import { useEffect, useState } from "react";
import { login } from "./api";

type TokenResponse = {
  access_token: string;
  refresh_token: string;
  role: string;
};

type ConsentItem = {
  id: string;
  patient_id: string;
  hiu_id: string;
  hip_id: string;
  status: string;
  valid_from: string;
  valid_to: string;
};

type RecordItem = {
  id: string;
  patient_id: string;
  record_type: string;
  uri: string;
  created_at: string;
};

function getToken(): string | null {
  return localStorage.getItem("access_token");
}

async function apiFetch(path: string, options: RequestInit = {}) {
  const token = getToken();
  const headers = new Headers(options.headers || {});
  headers.set("Content-Type", "application/json");
  if (token) {   
    headers.set("Authorization", `Bearer ${token}`);
  }
  const res = await fetch(`${import.meta.env.VITE_API_BASE || "http://localhost:8000"}${path}`, { ...options, headers });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  if (res.status === 204) return null;
  return res.json();
}

export default function App() {
  const [page, setPage] = useState("dashboard");
  const [isAuthed, setIsAuthed] = useState(Boolean(getToken()));
  const [consents, setConsents] = useState<ConsentItem[]>([]);
  const [records, setRecords] = useState<RecordItem[]>([]);
  const [patientId, setPatientId] = useState("");
  const [hiRequest, setHiRequest] = useState({
    transactionId: "",
    consentId: "",
    requestId: "",
    from: "",
    to: ""
  });
  const [hiResponse, setHiResponse] = useState<string>("");
  const [error, setError] = useState<string>("");

  useEffect(() => {
    if (!isAuthed) return;
    apiFetch("/api/consents")
      .then((data) => setConsents(data || []))
      .catch(() => setConsents([]));
  }, [isAuthed]);

  const handleLogin = async (email: string, password: string) => {
    setError("");
    const res = (await login(email, password)) as TokenResponse;
    localStorage.setItem("access_token", res.access_token);
    localStorage.setItem("refresh_token", res.refresh_token);
    localStorage.setItem("role", res.role);
    setIsAuthed(true);
  };

  const handleLogout = () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    localStorage.removeItem("role");
    setIsAuthed(false);
  };

  const loadRecords = async () => {
    if (!patientId) return;
    setError("");
    const data = (await apiFetch(`/api/patients/${patientId}/records`)) as RecordItem[];
    setRecords(data || []);
  };

  const submitHIRequest = async () => {
    setError("");
    setHiResponse("");
    const payload = {
      transactionId: hiRequest.transactionId,
      consentId: hiRequest.consentId,
      hiRequest: {
        requestId: hiRequest.requestId,
        timestamp: new Date().toISOString(),
        hiTypes: ["ImagingStudy"],
        dateRange: {
          from: hiRequest.from,
          to: hiRequest.to
        }
      }
    };
    const data = await apiFetch("/abdm/health-information/request", {
      method: "POST",
      body: JSON.stringify(payload)
    });
    setHiResponse(JSON.stringify(data, null, 2));
  };

  return (
    <div className="app">
      <aside className="sidebar">
        <h1>ABDM Colposcopy Console</h1>
        <div>
          <div className="badge">ABDM HIE-CM Integration</div>
        </div>
        <div className="nav">
          <button className={page === "dashboard" ? "active" : ""} onClick={() => setPage("dashboard")}>Dashboard</button>
          <button className={page === "consents" ? "active" : ""} onClick={() => setPage("consents")}>Consent Status</button>
          <button className={page === "records" ? "active" : ""} onClick={() => setPage("records")}>Patient Records</button>
          <button className={page === "hi-requests" ? "active" : ""} onClick={() => setPage("hi-requests")}>Health Info Requests</button>
        </div>
        {isAuthed && (
          <button className="primary" onClick={handleLogout}>Logout</button>
        )}
      </aside>
      <main className="content">
        <div className="topbar">
          <div>
            <h2>{page === "dashboard" ? "Dashboard" : page === "consents" ? "ABDM Consent Status" : page === "records" ? "Patient Records" : "Health Information Requests"}</h2>
            <p>Consent-governed health data access · Colposcope imaging backend</p>
          </div>
        </div>

        {!isAuthed && (
          <div className="card">
            <LoginForm onLogin={handleLogin} error={error} setError={setError} />
          </div>
        )}

        {isAuthed && page === "dashboard" && (
          <div className="grid">
            <div className="card">
              <h3>System Purpose</h3>
              <p>Clinical backend for colposcope devices storing metadata and consent-governed references.</p>
              <p>HIP/HIU interface aligned to ABDM Phase-1 sandbox rules.</p>
            </div>
            <div className="card">
              <h3>Security Posture</h3>
              <p>JWT auth, role-based access (ADMIN, DOCTOR, SUPERADMIN), audit logging, immutable consent store.</p>
            </div>
            <div className="card">
              <h3>Quick Actions</h3>
              <p>Use the Patient Records tab to query colposcope imaging metadata.</p>
            </div>
          </div>
        )}

        {isAuthed && page === "consents" && (
          <div className="card">
            <table className="table">
              <thead>
                <tr>
                  <th>Consent ID</th>
                  <th>Patient</th>
                  <th>HIU</th>
                  <th>HIP</th>
                  <th>Status</th>
                  <th>Valid From</th>
                  <th>Valid To</th>
                </tr>
              </thead>
              <tbody>
                {consents.map((consent) => (
                  <tr key={consent.id}>
                    <td>{consent.id}</td>
                    <td>{consent.patient_id}</td>
                    <td>{consent.hiu_id}</td>
                    <td>{consent.hip_id}</td>
                    <td>{consent.status}</td>
                    <td>{new Date(consent.valid_from).toLocaleString()}</td>
                    <td>{new Date(consent.valid_to).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {isAuthed && page === "records" && (
          <div className="card">
            <div className="grid">
              <div>
                <label>Patient ID</label>
                <input value={patientId} onChange={(e) => setPatientId(e.target.value)} placeholder="abha@abdm" />
              </div>
              <div style={{ alignSelf: "end" }}>
                <button className="primary" onClick={loadRecords}>Load Records</button>
              </div>
            </div>
            <table className="table" style={{ marginTop: 16 }}>
              <thead>
                <tr>
                  <th>Record ID</th>
                  <th>Type</th>
                  <th>URI</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {records.map((record) => (
                  <tr key={record.id}>
                    <td>{record.id}</td>
                    <td>{record.record_type}</td>
                    <td>{record.uri}</td>
                    <td>{new Date(record.created_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {isAuthed && page === "hi-requests" && (
          <div className="card">
            <div className="grid">
              <div>
                <label>Transaction ID</label>
                <input value={hiRequest.transactionId} onChange={(e) => setHiRequest({ ...hiRequest, transactionId: e.target.value })} />
              </div>
              <div>
                <label>Consent ID</label>
                <input value={hiRequest.consentId} onChange={(e) => setHiRequest({ ...hiRequest, consentId: e.target.value })} />
              </div>
              <div>
                <label>Request ID</label>
                <input value={hiRequest.requestId} onChange={(e) => setHiRequest({ ...hiRequest, requestId: e.target.value })} />
              </div>
              <div>
                <label>Date From (UTC)</label>
                <input value={hiRequest.from} onChange={(e) => setHiRequest({ ...hiRequest, from: e.target.value })} placeholder="2025-01-01T00:00:00Z" />
              </div>
              <div>
                <label>Date To (UTC)</label>
                <input value={hiRequest.to} onChange={(e) => setHiRequest({ ...hiRequest, to: e.target.value })} placeholder="2025-02-01T00:00:00Z" />
              </div>
            </div>
            <button className="primary" style={{ marginTop: 16 }} onClick={submitHIRequest}>Submit HI Request</button>
            {hiResponse && (
              <pre className="card" style={{ marginTop: 16 }}>{hiResponse}</pre>
            )}
          </div>
        )}

        {error && (
          <div className="card">
            <strong>Error:</strong> {error}
          </div>
        )}
      </main>
    </div>
  );
}

type LoginFormProps = {
  onLogin: (email: string, password: string) => void;
  error: string;
  setError: (value: string) => void;
};

function LoginForm({ onLogin, error, setError }: LoginFormProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    try {
      await onLogin(email, password);
    } catch (err) {
      setError((err as Error).message || "Login failed");
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <h3>Login</h3>
      <p>Authenticate using ABDM-integrated operator credentials.</p>
      <div className="grid">
        <div>
          <label>Email</label>
          <input value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        <div>
          <label>Password</label>
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        </div>
      </div>
      <button className="primary" style={{ marginTop: 16 }} type="submit">Login</button>
      {error && <p style={{ color: "#b02828" }}>{error}</p>}
    </form>
  );
}
