import React, { useState, useRef, useEffect, useCallback } from "react";
import ReactMarkdown from "react-markdown";

const API_BASE = "";

/* ================================================================
   Feature definitions (loaded from backend, with local fallback)
   ================================================================ */
const FALLBACK_FEATURES = [
  {
    id: "web_search",
    name: "🔍 Web Search",
    description:
      "Ask Claude a question and it will search the web for up-to-date information before answering.",
    category: "Tools",
    availableOn: "Available on Microsoft Foundry and Google Vertex only",
    hasInput: true,
    inputLabel: "Ask a question",
    inputPlaceholder: "What is Microsoft Foundry?",
  },
  {
    id: "web_fetch",
    name: "🌐 Web Fetch",
    description:
      "Retrieve full content from web pages and PDF documents for in-depth analysis without custom scraping infrastructure.​",
    category: "Tools",
    exclusive: true,
    hasInput: true,
    inputLabel: "Enter a URL to analyze",
    inputPlaceholder:
      "Please analyze the content at https://learn.microsoft.com/en-us/azure/ai-foundry/what-is-foundry?view=foundry&preserve-view=true",
  },
  {
    id: "files_api",
    name: "📎 Files API",
    description:
      "Upload files once and reference across unlimited API calls. Reduces bandwidth costs by up to 90% for document-heavy applications.",
    category: "Core",
    exclusive: true,
    hasInput: true,
    hasFileUpload: true,
    inputLabel: "Ask a question about the uploaded file",
    inputPlaceholder: "Please summarize this document for me.",
  },
  {
    id: "code_execution",
    name: "💻 Code Execution and Programmatic Tool Calling",
    description:
      "Run Python in sandboxed environments for data analysis without external infrastructure. With PTC, Claude calls tools directly from code containers, reducing token use by 40% and latency by 60%.",
    category: "Tools",
    exclusive: true,
    scenario: "In this scenario, we need to analyze team expenses and identify which employees have exceeded their budgets. Traditionally, we might manually pull expense reports for each person, sum up their expenses by category, compare against budget limits (checking for custom budget exceptions), and compile a report. Instead, we will ask Claude to perform this analysis for us, using the available tools to retrieve team data, fetch potentially hundreds of expense line items with rich metadata, and determine who has gone over budget.",
    hasInput: true,
    inputLabel: "Ask a question about team expenses.Click on the scenario button to understand more on the context.",
    inputPlaceholder:
      "Which engineering team members exceeded their Q3 travel budget? Standard quarterly travel budget is $5,000. However, some employees have custom budget limits. For anyone who exceeded the $5,000 standard budget, check if they have a custom budget exception.",
  },
  {
    id: "prompt_caching",
    name: "⚡ Prompt Caching",
    description:
      "See how 1-hour prompt caching reduces latency and cost on repeated queries.Extended cache duration supports intermittent workloads (6-60 minuteintervals)",
    category: "Core",
    exclusive: true,
    hasInput: true,
    inputReadOnly: true,
    inputLabel: "Question",
    inputPlaceholder: "Revenue in 2025? Only return the value using Microsoft Annual report 2025",
  },
  {
    id: "skills",
    name: "🛠️ Document Generation",
    description:
      "Build agents that create PowerPoint presentations, Excel spreadsheets, Word documents, and PDFs programmatically through API calls.​It helps eliminate manual document creation workflows and enables documentautomation at enterprise scale.",
    category: "Agent Skills",
    exclusive: true,
    hasInput: true,
    inputLabel: "Describe the document you want",
    inputPlaceholder:
      "Write a 2-page report on the benefits of agentic AI architecture",
    subFeatures: [
      {
        id: "generate_docx",
        name: "📄 Word Document",
        description: "Generate a .docx file",
        inputPlaceholder:
          "Write a 2-page report on the benefits of agentic AI architecture",
      },
      {
        id: "generate_pdf",
        name: "📕 PDF Document",
        description: "Generate a .pdf file",
        inputPlaceholder: "Generate a PDF invoice template",
      },
    ],
  },
];

export default function App() {
  const [features, setFeatures] = useState(FALLBACK_FEATURES);
  const [selected, setSelected] = useState(null);
  const [activeSubFeature, setActiveSubFeature] = useState(null);
  const [input, setInput] = useState("");
  const [output, setOutput] = useState("");
  const [status, setStatus] = useState("");
  const [statusType, setStatusType] = useState(""); // "", "error", "success"
  const [running, setRunning] = useState(false);
  const [downloadFile, setDownloadFile] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [uploadKey, setUploadKey] = useState(null);
  const [uploadedFileName, setUploadedFileName] = useState("");
  const [uploading, setUploading] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [cacheCountdown, setCacheCountdown] = useState(null);
  const outputRef = useRef(null);
  const timerRef = useRef(null);
  const countdownRef = useRef(null);
  const cacheStartTimesRef = useRef({});  // { started: timestamp }
  const [collapsedCategories, setCollapsedCategories] = useState({});

  // --- Configuration state ---
  const [configured, setConfigured] = useState(false);
  const [configLoading, setConfigLoading] = useState(true); // true while checking backend
  const [configError, setConfigError] = useState("");
  const [endpoint, setEndpoint] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [modelList, setModelList] = useState([]);
  const [selectedModel, setSelectedModel] = useState("");
  const [configuring, setConfiguring] = useState(false);
  const [connectedModel, setConnectedModel] = useState("");
  const [connectedEndpoint, setConnectedEndpoint] = useState("");
  const [showScenario, setShowScenario] = useState(false);

  // Group features by category (preserving order)
  const groupedFeatures = React.useMemo(() => {
    const groups = [];
    const seen = new Set();
    for (const f of features) {
      const cat = f.category || "Other";
      if (!seen.has(cat)) {
        seen.add(cat);
        groups.push({ category: cat, items: [] });
      }
      groups.find((g) => g.category === cat).items.push(f);
    }
    return groups;
  }, [features]);

  const toggleCategory = useCallback((cat) => {
    setCollapsedCategories((prev) => ({ ...prev, [cat]: !prev[cat] }));
  }, []);

  // Load model list on mount – always show config screen for fresh setup
  useEffect(() => {
    fetch(`${API_BASE}/api/models`)
      .then((r) => r.json())
      .then((models) => {
        setModelList(models);
        if (models.length > 0) setSelectedModel(models[0]);
        setConfigLoading(false);
      })
      .catch(() => {
        setConfigLoading(false);
      });
  }, []);

  const handleConfigure = useCallback(async () => {
    setConfigError("");
    if (!endpoint.trim() || !apiKey.trim() || !selectedModel) {
      setConfigError("All fields are required.");
      return;
    }
    setConfiguring(true);
    try {
      const res = await fetch(`${API_BASE}/api/configure`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ endpoint: endpoint.trim(), apiKey: apiKey.trim(), model: selectedModel }),
      });
      const data = await res.json();
      if (data.error) {
        setConfigError(data.error);
      } else {
        setConfigured(true);
        setConnectedModel(selectedModel);
        setConnectedEndpoint(endpoint.trim());
        // Reload features from backend now that it's configured
        fetch(`${API_BASE}/api/features`)
          .then((r) => r.json())
          .then(setFeatures)
          .catch(() => {});
      }
    } catch (err) {
      setConfigError(`Connection error: ${err.message}`);
    }
    setConfiguring(false);
  }, [endpoint, apiKey, selectedModel]);

  const handleDisconnect = useCallback(() => {
    setConfigured(false);
    setSelected(null);
    setOutput("");
    setStatus("");
    setStatusType("");
    setConnectedModel("");
    setConnectedEndpoint("");
  }, []);

  // Load features from backend
  useEffect(() => {
    fetch(`${API_BASE}/api/features`)
      .then((r) => r.json())
      .then(setFeatures)
      .catch(() => {}); // fallback already set
  }, []);

  // Auto-scroll output
  useEffect(() => {
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }
  }, [output]);

  // Timer
  useEffect(() => {
    if (running) {
      setElapsed(0);
      const start = Date.now();
      timerRef.current = setInterval(
        () => setElapsed(((Date.now() - start) / 1000).toFixed(1)),
        100
      );
    } else {
      clearInterval(timerRef.current);
    }
    return () => clearInterval(timerRef.current);
  }, [running]);

  // Cache countdown timer
  useEffect(() => {
    if (cacheCountdown !== null && cacheCountdown > 0) {
      countdownRef.current = setInterval(() => {
        setCacheCountdown((prev) => {
          if (prev <= 1) {
            clearInterval(countdownRef.current);
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    }
    return () => clearInterval(countdownRef.current);
  }, [cacheCountdown !== null && cacheCountdown > 0]);

  const selectFeature = useCallback(
    (f) => {
      if (running || !configured) return;
      setSelected(f);
      // Auto-select first sub-feature if available
      const firstSub = f.subFeatures?.[0] || null;
      setActiveSubFeature(firstSub);
      setInput((firstSub?.inputPlaceholder) || f.inputPlaceholder || "");
      setOutput("");
      setStatus("");
      setStatusType("");
      setDownloadFile(null);
      setMetrics(null);
      setShowScenario(false);
      setCacheCountdown(null);
      cacheStartTimesRef.current = {};  // Reset timer tracking on feature switch
      setUploadKey(null);
      setUploadedFileName("");
    },
    [running, configured]
  );

  const selectSubFeature = useCallback(
    (sub) => {
      if (running) return;
      setActiveSubFeature(sub);
      setInput(sub.inputPlaceholder || "");
      setOutput("");
      setStatus("");
      setStatusType("");
      setDownloadFile(null);
      setMetrics(null);
      // Don't reset countdown — keep timer running across sub-feature switches
      setUploadKey(null);
      setUploadedFileName("");
    },
    [running]
  );

  const handleFileUpload = useCallback(async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setStatus(`Uploading ${file.name}...`);
    setStatusType("");
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch(`${API_BASE}/api/upload`, {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      if (data.error) {
        setStatus(`Upload failed: ${data.error}`);
        setStatusType("error");
      } else {
        setUploadKey(data.uploadKey);
        setUploadedFileName(data.filename);
        setStatus(`✅ ${data.filename} uploaded successfully`);
        setStatusType("success");
      }
    } catch (err) {
      setStatus(`Upload error: ${err.message}`);
      setStatusType("error");
    }
    setUploading(false);
  }, []);

  const runFeature = useCallback(() => {
    if (!selected || running) return;
    // Use the sub-feature id if one is selected, otherwise the parent
    const featureId = activeSubFeature?.id || selected.id;

    setRunning(true);
    setOutput("");
    setStatus("Connecting...");
    setStatusType("");
    setDownloadFile(null);
    setMetrics(null);
    setMetrics(null);

    fetch(`${API_BASE}/api/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ featureId, input, uploadKey }),
    })
      .then((response) => {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        function processChunk({ done, value }) {
          if (done) {
            setRunning(false);
            return;
          }

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop(); // keep incomplete line

          let currentEvent = null;
          for (const line of lines) {
            if (line.startsWith("event: ")) {
              currentEvent = line.slice(7);
            } else if (line.startsWith("data: ") && currentEvent) {
              try {
                const data = JSON.parse(line.slice(6));

                switch (currentEvent) {
                  case "token":
                    setOutput((prev) => prev + data.text);
                    break;
                  case "status":
                    setStatus(data.message);
                    setStatusType("");
                    break;
                  case "file":
                    setDownloadFile(data);
                    break;
                  case "metrics":
                    setMetrics(data);
                    // Start or resume 1-hour cache countdown timer
                    if (data.cache_type) {
                      const totalSeconds = 3600;
                      if (cacheStartTimesRef.current.started) {
                        const elapsedSec = Math.floor((Date.now() - cacheStartTimesRef.current.started) / 1000);
                        if (elapsedSec >= totalSeconds) {
                          // Cache expired — reset
                          cacheStartTimesRef.current.started = null;
                        }
                      }
                      if (!cacheStartTimesRef.current.started) {
                        cacheStartTimesRef.current.started = Date.now();
                        setCacheCountdown(totalSeconds);
                      } else {
                        const elapsedSec = Math.floor((Date.now() - cacheStartTimesRef.current.started) / 1000);
                        setCacheCountdown(Math.max(0, totalSeconds - elapsedSec));
                      }
                    }
                    break;
                  case "error":
                    setStatus(data.message);
                    setStatusType("error");
                    break;
                  case "done":
                    setStatus(data.message);
                    setStatusType("success");
                    setRunning(false);
                    break;
                  default:
                    break;
                }
              } catch {
                // ignore parse errors
              }
              currentEvent = null;
            }
          }

          return reader.read().then(processChunk);
        }

        return reader.read().then(processChunk);
      })
      .catch((err) => {
        setStatus(`Connection error: ${err.message}`);
        setStatusType("error");
        setRunning(false);
      });
  }, [selected, input, running, uploadKey, activeSubFeature]);

  return (
    <div className="app">
      {/* Header */}
      <header className="header">
        <img src="/claude_icon.png" alt="Claude | Microsoft Azure" className="header-logo-img" />
        <div className="header-text">
          <h1>Why Anthropic on Foundry?</h1>
          <p>
            Interactive explorer for Claude capabilities on Azure AI Foundry
          </p>
        </div>
      </header>

      <div className="main">
        {/* Sidebar */}
        <aside className="sidebar">
          {configured && (
            <div className="config-badge">
              <div className="config-badge-info">
                <span className="config-badge-dot" />
                <div>
                  <div className="config-badge-model">{connectedModel}</div>
                  <div className="config-badge-endpoint" title={connectedEndpoint}>
                    {connectedEndpoint.length > 35
                      ? connectedEndpoint.slice(0, 35) + "…"
                      : connectedEndpoint}
                  </div>
                </div>
              </div>
              <button className="disconnect-btn" onClick={handleDisconnect} title="Disconnect">
                ✕
              </button>
            </div>
          )}
          <div className="sidebar-title">Features</div>
          <div className={`feature-list ${!configured ? "disabled-features" : ""}`}>
            {groupedFeatures.map((group) => (
              <div key={group.category} className="category-group">
                <div
                  className="category-header"
                  onClick={() => toggleCategory(group.category)}
                >
                  <span className="category-arrow">
                    {collapsedCategories[group.category] ? "▶" : "▼"}
                  </span>
                  <span className="category-label">{group.category}</span>
                  <span className="category-count">{group.items.length}</span>
                </div>
                {!collapsedCategories[group.category] && (
                  <ul className="category-items">
                    {group.items.map((f) => (
                      <li
                        key={f.id}
                        className={`feature-item ${
                          selected?.id === f.id ? "active" : ""
                        }`}
                        onClick={() => selectFeature(f)}
                      >
                        <div className="name">{f.name}</div>
                        <div className="desc">{f.description}</div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        </aside>

        {/* Content */}
        <section className="content">
          {!configured ? (
            <div className="config-screen">
              <div className="config-card">
                <div className="config-icon">🔑</div>
                <h2>Connect to Claude</h2>
                <p className="config-subtitle">
                  Enter your Anthropic on Azure AI Foundry endpoint, API key, and
                  select a model to get started.
                </p>

                {configLoading ? (
                  <div className="config-loading">Checking connection…</div>
                ) : (
                  <>
                    <div className="config-field">
                      <label>Endpoint URL</label>
                      <input
                        type="text"
                        value={endpoint}
                        onChange={(e) => setEndpoint(e.target.value)}
                        placeholder="https://your-resource.services.ai.azure.com/anthropic"
                        disabled={configuring}
                      />
                    </div>

                    <div className="config-field">
                      <label>API Key</label>
                      <input
                        type="password"
                        value={apiKey}
                        onChange={(e) => setApiKey(e.target.value)}
                        placeholder="Enter your API key"
                        disabled={configuring}
                      />
                    </div>

                    <div className="config-field">
                      <label>Model / Deployment</label>
                      <select
                        value={selectedModel}
                        onChange={(e) => setSelectedModel(e.target.value)}
                        disabled={configuring}
                      >
                        {modelList.map((m) => (
                          <option key={m} value={m}>
                            {m}
                          </option>
                        ))}
                      </select>
                    </div>

                    {configError && (
                      <div className="config-error">{configError}</div>
                    )}

                    <button
                      className="config-connect-btn"
                      onClick={handleConfigure}
                      disabled={configuring}
                    >
                      {configuring ? "Connecting…" : "Connect"}
                    </button>
                  </>
                )}
              </div>
            </div>
          ) : !selected ? (
            <div className="empty-state">
              <div className="icon">⚡</div>
              <p>Select a feature from the sidebar to get started</p>
            </div>
          ) : (
            <>
              {/* Feature title */}
              <div className="feature-header">
                <h2>
                  {selected.name}
                  {selected.exclusive && (
                    <span className="exclusive-badge">Exclusive to Microsoft Foundry</span>
                  )}
                  {selected.availableOn && (
                    <span className="available-badge">{selected.availableOn}</span>
                  )}
                </h2>
                <div className="feature-header-row">
                  <p>{selected.description}</p>
                  {selected.scenario && (
                    <button
                      className="scenario-btn"
                      onClick={() => setShowScenario(true)}
                    >
                      📋 Scenario
                    </button>
                  )}
                </div>
              </div>

              {/* Scenario modal */}
              {showScenario && selected.scenario && (
                <div className="modal-overlay" onClick={() => setShowScenario(false)}>
                  <div className="modal-card" onClick={(e) => e.stopPropagation()}>
                    <div className="modal-header">
                      <h3>📋 Scenario Context</h3>
                      <button className="modal-close" onClick={() => setShowScenario(false)}>✕</button>
                    </div>
                    <div className="modal-body">
                      <p>{selected.scenario}</p>
                    </div>
                  </div>
                </div>
              )}

              {/* Sub-feature tabs */}
              {selected.subFeatures && (
                <div className="sub-feature-tabs">
                  {selected.subFeatures.map((sub) => (
                    <button
                      key={sub.id}
                      className={`sub-tab ${activeSubFeature?.id === sub.id ? "active" : ""}`}
                      onClick={() => selectSubFeature(sub)}
                      disabled={running}
                    >
                      {sub.name}
                    </button>
                  ))}
                </div>
              )}

              {/* File upload */}
              {selected.hasFileUpload && (
                <div className="file-upload-area">
                  <label className="file-upload-label">
                    <input
                      type="file"
                      onChange={handleFileUpload}
                      disabled={running || uploading}
                      accept=".pdf,.docx,.doc,.txt,.csv,.md,.json,.xlsx,.pptx"
                      style={{ display: "none" }}
                    />
                    <span className={`file-upload-btn ${uploading ? "uploading" : ""}`}>
                      {uploading ? "⏳ Uploading..." : uploadedFileName ? `📎 ${uploadedFileName}` : "📁 Choose a file to upload"}
                    </span>
                  </label>
                  {uploadedFileName && (
                    <span className="file-upload-check">✅</span>
                  )}
                </div>
              )}

              {/* Input */}
              {selected.hasInput && (
                <div className="input-area">
                  <label>{selected.inputLabel}</label>
                  <div className="input-row">
                    <textarea
                      value={input}
                      onChange={(e) => { if (!selected.inputReadOnly) setInput(e.target.value); }}
                      placeholder={activeSubFeature?.inputPlaceholder || selected.inputPlaceholder}
                      disabled={running}
                      readOnly={selected.inputReadOnly || false}
                      className={selected.inputReadOnly ? "input-readonly" : ""}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && !e.shiftKey) {
                          e.preventDefault();
                          runFeature();
                        }
                      }}
                    />
                    <button
                      className="run-btn"
                      onClick={runFeature}
                      disabled={running || (selected.hasFileUpload && !uploadKey)}
                    >
                      {running ? "Running…" : "▶ Run"}
                    </button>
                  </div>
                </div>
              )}

              {!selected.hasInput && (
                <div style={{ marginBottom: 20 }}>
                  <button
                    className="run-btn"
                    onClick={runFeature}
                    disabled={running}
                  >
                    {running ? "Running…" : "▶ Run"}
                  </button>
                </div>
              )}

              {/* Performance Metrics */}
                {metrics && (
                  <div className="metrics-panel">
                    <div className="metrics-title">📊 Performance Metrics</div>

                    {/* Comparison table (code execution / PTC) */}
                    {metrics.comparison && metrics.rows && (
                      <>
                        <table className="comparison-table">
                          <thead>
                            <tr>
                              <th>Metric</th>
                              <th>Traditional</th>
                              <th className="ptc-col">PTC</th>
                            </tr>
                          </thead>
                          <tbody>
                            {metrics.rows.map((row, i) => (
                              <tr key={i} className={row.metric.includes("Reduction") ? "highlight-row" : ""}>
                                <td className="metric-name">{row.metric}</td>
                                <td>{row.traditional}</td>
                                <td className="ptc-col">{row.ptc}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                        <div className="metrics-hint">
                          Traditional = standard tool-calling loop &nbsp;|&nbsp; PTC = Programmatic Tool Calling (tools called from code execution container)
                        </div>
                      </>
                    )}

                    {/* Cache metrics (prompt caching) */}
                    {!metrics.comparison && (
                      <>
                        {cacheCountdown !== null && (
                          <div className="cache-countdown">
                            <div className="countdown-label">⏳ Cache expires in</div>
                            <div className={`countdown-value ${cacheCountdown === 0 ? "expired" : ""}`}>
                              {cacheCountdown === 0
                                ? "Expired"
                                : `${Math.floor(cacheCountdown / 3600).toString().padStart(2, "0")}:${Math.floor((cacheCountdown % 3600) / 60).toString().padStart(2, "0")}:${(cacheCountdown % 60).toString().padStart(2, "0")}`
                              }
                            </div>
                            <div className="countdown-bar">
                              <div
                                className="countdown-bar-fill"
                                style={{
                                  width: `${(cacheCountdown / 3600) * 100}%`,
                                }}
                              />
                            </div>
                          </div>
                        )}
                        <div className="metrics-grid">
                          <div className="metric-card">
                            <div className="metric-value">{metrics.cache_status}</div>
                            <div className="metric-label">Cache Status</div>
                          </div>
                          <div className="metric-card">
                            <div className="metric-value">{metrics.non_cached_time_seconds}s</div>
                            <div className="metric-label">Non-Cached Time</div>
                          </div>
                          <div className="metric-card">
                            <div className="metric-value">{metrics.response_time_seconds != null ? `${metrics.response_time_seconds}s` : '—'}</div>
                            <div className="metric-label">Cached Time</div>
                          </div>
                          <div className="metric-card highlight">
                            <div className="metric-value">{metrics.speedup}</div>
                            <div className="metric-label">Speedup</div>
                          </div>
                          <div className="metric-card">
                            <div className="metric-value">{metrics.input_tokens}</div>
                            <div className="metric-label">Input Tokens</div>
                          </div>
                          <div className="metric-card">
                            <div className="metric-value">{metrics.output_tokens}</div>
                            <div className="metric-label">Output Tokens</div>
                          </div>
                          <div className="metric-card">
                            <div className="metric-value">{metrics.cache_creation_input_tokens}</div>
                            <div className="metric-label">Cache Created Tokens</div>
                          </div>
                          <div className="metric-card">
                            <div className="metric-value">{metrics.cache_read_input_tokens}</div>
                            <div className="metric-label">Cache Read Tokens</div>
                          </div>
                        </div>
                        <div className="metrics-hint">
                          {metrics.cache_type} cache — Run the same query again to see cache HIT and faster response times.
                        </div>
                      </>
                    )}
                  </div>
                )}

              {/* Output */}
              <div className="output-area">
                <div className="output-label">
                  {running && <span className="live-dot" />}
                  Response
                  {running && (
                    <span className="timer">{elapsed}s</span>
                  )}
                </div>

                {/* Download button */}
                {downloadFile && (
                  <a
                    className="download-btn"
                    href={`${API_BASE}/api/download/${downloadFile.filename}`}
                    download
                  >
                    📥 Download {downloadFile.fileType.toUpperCase()} File
                  </a>
                )}

                <div
                  className={`output-box ${running ? "streaming" : ""}`}
                  ref={outputRef}
                >
                  {output ? (
                    <>
                      <ReactMarkdown>{output}</ReactMarkdown>
                      {running && <span className="cursor" />}
                    </>
                  ) : running ? (
                    <span style={{ color: "var(--text-muted)" }}>
                      Waiting for response…
                    </span>
                  ) : (
                    <span style={{ color: "var(--text-muted)" }}>
                      Click "Run" to execute this feature
                    </span>
                  )}
                </div>

                {/* Status bar */}
                {status && (
                  <div className={`status-bar ${statusType}`}>
                    {running && <span className="spinner" />}
                    {status}
                  </div>
                )}
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  );
}
