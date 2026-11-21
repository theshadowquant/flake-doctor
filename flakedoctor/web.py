"""Flake Doctor Live Local Web Dashboard.

Zero external dependencies - built entirely on Python standard library http.server.
"""
from __future__ import annotations

import ast
import json
import os
import shutil
import time
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List

from .ast_analyzer import analyze_test
from .engine import TestReport, diagnose
from .patcher import build_patch


HTML_DASHBOARD = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Flake Doctor | Forensic Root-Cause Console</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #0b0f19;
      --card-bg: #111827;
      --card-border: #1f2937;
      --accent: #3b82f6;
      --accent-hover: #2563eb;
      --text: #f3f4f6;
      --text-dim: #9ca3af;
      --polluter: #f97316;
      --order-dep: #c084fc;
      --prng: #facc15;
      --timing: #38bdf8;
      --broken: #ef4444;
      --stable: #10b981;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: var(--bg);
      color: var(--text);
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      min-height: 100vh;
      padding-bottom: 60px;
    }
    code, pre, .mono { font-family: 'JetBrains Mono', monospace; }

    header {
      background: linear-gradient(180deg, #131b2e 0%, #0b0f19 100%);
      border-bottom: 1px solid var(--card-border);
      padding: 24px 36px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 14px;
    }
    .logo-badge {
      background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
      color: white;
      font-weight: 800;
      font-size: 18px;
      padding: 8px 14px;
      border-radius: 8px;
      letter-spacing: 1px;
    }
    .brand h1 { font-size: 22px; font-weight: 800; letter-spacing: -0.5px; }
    .brand span { color: var(--text-dim); font-size: 13px; font-weight: 500; }
    .live-status {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 13px;
      color: #34d399;
      background: rgba(16, 185, 129, 0.1);
      padding: 6px 14px;
      border-radius: 20px;
      border: 1px solid rgba(16, 185, 129, 0.2);
    }
    .pulse-dot {
      width: 8px; height: 8px; border-radius: 50%;
      background: #10b981;
      box-shadow: 0 0 10px #10b981;
      animation: pulse 2s infinite;
    }
    @keyframes pulse { 0% { opacity: 0.4; } 50% { opacity: 1; } 100% { opacity: 0.4; } }

    main { max-width: 1320px; margin: 32px auto; padding: 0 24px; }

    .pipeline-banner {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      padding: 20px 28px;
      margin-bottom: 28px;
    }
    .pipeline-title {
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 1.5px;
      color: var(--text-dim);
      margin-bottom: 14px;
      font-weight: 700;
    }
    .pipeline-grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 16px;
      position: relative;
    }
    .pipeline-step {
      background: rgba(255, 255, 255, 0.02);
      border: 1px solid rgba(255, 255, 255, 0.05);
      border-radius: 8px;
      padding: 12px 16px;
    }
    .pipeline-step h3 { font-size: 13px; font-weight: 700; color: #93c5fd; margin-bottom: 4px; }
    .pipeline-step p { font-size: 11px; color: var(--text-dim); line-height: 1.4; }

    .control-panel {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      padding: 24px;
      margin-bottom: 28px;
    }
    .controls-row {
      display: flex;
      gap: 16px;
      align-items: center;
      margin-bottom: 18px;
      flex-wrap: wrap;
    }
    select, input, button {
      font-family: inherit;
    }
    .file-select {
      flex: 1;
      min-width: 280px;
      background: #1f2937;
      color: white;
      border: 1px solid #374151;
      padding: 12px 16px;
      border-radius: 8px;
      font-size: 14px;
      cursor: pointer;
    }
    .btn {
      padding: 12px 20px;
      border-radius: 8px;
      font-size: 13px;
      font-weight: 700;
      border: none;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 8px;
      transition: all 0.15s ease;
    }
    .btn-primary { background: var(--accent); color: white; }
    .btn-primary:hover { background: var(--accent-hover); transform: translateY(-1px); }
    .btn-purple { background: #8b5cf6; color: white; }
    .btn-purple:hover { background: #7c3aed; transform: translateY(-1px); }
    .btn-green { background: #059669; color: white; }
    .btn-green:hover { background: #047857; transform: translateY(-1px); }
    .btn-outline { background: transparent; border: 1px solid #4b5563; color: #d1d5db; }
    .btn-outline:hover { background: rgba(255,255,255,0.05); color: white; }
    .btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }

    .editor-card {
      background: #0d1117;
      border: 1px solid #30363d;
      border-radius: 8px;
      overflow: hidden;
      margin-bottom: 8px;
    }
    .editor-header {
      background: #161b22;
      padding: 8px 16px;
      font-size: 12px;
      color: #8b949e;
      display: flex;
      justify-content: space-between;
      border-bottom: 1px solid #30363d;
    }
    textarea.code-editor {
      width: 100%;
      height: 180px;
      background: #0d1117;
      color: #e6edf3;
      border: none;
      padding: 14px 16px;
      font-size: 13px;
      line-height: 1.5;
      resize: vertical;
      outline: none;
    }

    .status-alert {
      padding: 14px 20px;
      border-radius: 8px;
      font-size: 14px;
      font-weight: 500;
      display: none;
      margin-bottom: 24px;
    }
    .status-alert.active { display: block; }
    .status-alert.loading { background: rgba(59, 130, 246, 0.15); border: 1px solid #3b82f6; color: #93c5fd; }
    .status-alert.success { background: rgba(16, 185, 129, 0.15); border: 1px solid #10b981; color: #6ee7b7; }
    .status-alert.error { background: rgba(239, 68, 68, 0.15); border: 1px solid #ef4444; color: #fca5a5; }

    .summary-metrics {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 16px;
      margin-bottom: 28px;
      display: none;
    }
    .metric-card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 10px;
      padding: 16px 20px;
    }
    .metric-title { font-size: 11px; text-transform: uppercase; color: var(--text-dim); font-weight: 700; margin-bottom: 6px; }
    .metric-val { font-size: 24px; font-weight: 800; color: white; }

    .autopsy-section h2 { font-size: 18px; margin-bottom: 16px; font-weight: 700; }
    .test-card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 10px;
      padding: 20px;
      margin-bottom: 16px;
      transition: border-color 0.15s ease;
    }
    .test-card:hover { border-color: #374151; }
    .test-card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;
      flex-wrap: wrap;
      gap: 10px;
    }
    .test-name { font-size: 16px; font-weight: 700; }
    .badge {
      display: inline-block;
      padding: 4px 10px;
      border-radius: 6px;
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.5px;
    }
    .badge-POLLUTER { background: rgba(249, 115, 22, 0.15); color: var(--polluter); border: 1px solid var(--polluter); }
    .badge-ORDER_DEPENDENT { background: rgba(192, 132, 252, 0.15); color: var(--order-dep); border: 1px solid var(--order-dep); }
    .badge-FLAKY_PRNG { background: rgba(250, 204, 21, 0.15); color: var(--prng); border: 1px solid var(--prng); }
    .badge-FLAKY_TIMING { background: rgba(56, 189, 248, 0.15); color: var(--timing); border: 1px solid var(--timing); }
    .badge-BROKEN_BUILD { background: rgba(239, 68, 68, 0.15); color: var(--broken); border: 1px solid var(--broken); }
    .badge-STABLE { background: rgba(16, 185, 129, 0.15); color: var(--stable); border: 1px solid var(--stable); }

    .test-body-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;
      font-size: 13px;
    }
    @media(max-width: 860px) { .test-body-grid { grid-template-columns: 1fr; } }
    .info-pane {
      background: rgba(0,0,0,0.2);
      border-radius: 8px;
      padding: 12px 14px;
      border: 1px solid rgba(255,255,255,0.04);
    }
    .info-label { font-size: 11px; text-transform: uppercase; color: var(--text-dim); margin-bottom: 4px; font-weight: 700; }
    .info-val { color: #d1d5db; line-height: 1.4; }
    .snippet-box {
      margin-top: 6px;
      background: #0d1117;
      padding: 8px 10px;
      border-radius: 6px;
      font-size: 12px;
      color: #93c5fd;
      border: 1px solid #30363d;
      white-space: pre-wrap;
    }

    .diff-section {
      margin-top: 28px;
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      padding: 24px;
      display: none;
    }
    .diff-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 14px;
    }
    pre.diff-view {
      background: #0d1117;
      border: 1px solid #30363d;
      border-radius: 8px;
      padding: 16px;
      overflow-x: auto;
      font-size: 12px;
      line-height: 1.6;
    }
    .diff-add { color: #34d399; }
    .diff-del { color: #f87171; }
    .diff-hunk { color: #60a5fa; }

    .after-fix-table {
      width: 100%;
      border-collapse: collapse;
      margin-top: 14px;
      font-size: 13px;
    }
    .after-fix-table th, .after-fix-table td {
      padding: 10px 14px;
      text-align: left;
      border-bottom: 1px solid #1f2937;
    }
    .after-fix-table th { background: rgba(255,255,255,0.03); color: var(--text-dim); font-size: 11px; text-transform: uppercase; }
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <div class="logo-badge">FD</div>
      <div>
        <h1>Flake Doctor</h1>
        <span>Autonomous Test Forensic Engine & Closed-Loop Healer</span>
      </div>
    </div>
    <div class="live-status">
      <div class="pulse-dot"></div>
      <span>Forensic Daemon Ready</span>
    </div>
  </header>

  <main>
    <div class="pipeline-banner">
      <div class="pipeline-title">Deterministic Forensic Pipeline</div>
      <div class="pipeline-grid">
        <div class="pipeline-step">
          <h3>1. Perturbation Engine</h3>
          <p>8-seed PRNG sweep + 6-level thread delay jitter injection isolate non-determinism.</p>
        </div>
        <div class="pipeline-step">
          <h3>2. Binary Order Bisector</h3>
          <p>O(log N) bisection pinpoints state polluter tests leaking memory or env vars.</p>
        </div>
        <div class="pipeline-step">
          <h3>3. Python AST X-Ray</h3>
          <p>Static AST locator extracts offending statements & calculates 99% confidence runs.</p>
        </div>
        <div class="pipeline-step">
          <h3>4. Closed-Loop Auto-Patcher</h3>
          <p>Rewrites fixtures/monkeypatches and proves cure without masking real bugs.</p>
        </div>
      </div>
    </div>

    <div class="control-panel">
      <div class="controls-row">
        <select id="fileDropdown" class="file-select" onchange="onFileSelected()">
          <option value="" disabled selected>Loading test files...</option>
        </select>
        <button id="btnScan" class="btn btn-primary" onclick="runScan()">
          <span>&#9654;</span> Run Forensic Scan
        </button>
        <button id="btnPatch" class="btn btn-purple" onclick="previewPatch()" disabled>
          <span>&#9874;</span> Preview AST Patch
        </button>
        <button id="btnApply" class="btn btn-green" onclick="applyFix()" disabled>
          <span>&#10003;</span> Apply Fix & Verify Cure
        </button>
        <button id="btnRestore" class="btn btn-outline" onclick="restoreOriginal()" disabled>
          <span>&#8634;</span> Restore Original File
        </button>
      </div>

      <div class="editor-card">
        <div class="editor-header">
          <span id="editorLabel">Active Test Source Code</span>
          <span id="editorStatus">Read-Only</span>
        </div>
        <textarea id="codeEditor" class="code-editor mono" spellcheck="false" placeholder="Select a file or paste custom pytest code..."></textarea>
      </div>
    </div>

    <div id="statusAlert" class="status-alert"></div>

    <div id="metricsRow" class="summary-metrics">
      <div class="metric-card">
        <div class="metric-title">Scan Elapsed Time</div>
        <div id="metricTime" class="metric-val mono">-</div>
      </div>
      <div class="metric-card">
        <div class="metric-title">Subprocess Invocations</div>
        <div id="metricSubs" class="metric-val mono">-</div>
      </div>
      <div class="metric-card">
        <div class="metric-title">Tests Diagnosed</div>
        <div id="metricTests" class="metric-val mono">-</div>
      </div>
      <div class="metric-card">
        <div class="metric-title">Cure Rate / Status</div>
        <div id="metricCure" class="metric-val mono" style="color: #34d399;">-</div>
      </div>
    </div>

    <div id="autopsySection" class="autopsy-section" style="display: none;">
      <h2>Forensic Autopsy Results</h2>
      <div id="cardsContainer"></div>
    </div>

    <div id="diffSection" class="diff-section">
      <div class="diff-header">
        <h2>AST Unified Diff (fixes.patch)</h2>
        <span class="mono" style="font-size: 12px; color: var(--text-dim);" id="diffFileLabel"></span>
      </div>
      <pre id="diffViewer" class="diff-view mono"></pre>

      <div id="afterFixContainer" style="margin-top: 24px; display: none;">
        <h3 style="font-size: 15px; margin-bottom: 8px; color: #93c5fd;">Closed-Loop Fix Verification</h3>
        <table class="after-fix-table">
          <thead>
            <tr>
              <th>Test Function</th>
              <th>Before Verdict</th>
              <th>After Verdict</th>
            </tr>
          </thead>
          <tbody id="afterFixBody"></tbody>
        </table>
        <div id="healSummary" style="margin-top: 12px; font-weight: 700; color: #34d399;"></div>
      </div>
    </div>
  </main>

  <script>
    let filesCache = {};
    let currentReports = null;
    let currentDiff = null;

    async function loadFiles() {
      try {
        const res = await fetch('/api/files');
        const data = await res.json();
        filesCache = {};
        const sel = document.getElementById('fileDropdown');
        sel.innerHTML = '';

        data.files.forEach((f, i) => {
          filesCache[f.path] = f.content;
          const opt = document.createElement('option');
          opt.value = f.path;
          opt.textContent = `${f.path}`;
          if (i === 0) opt.selected = true;
          sel.appendChild(opt);
        });

        // Add custom code option
        const customOpt = document.createElement('option');
        customOpt.value = "__CUSTOM__";
        customOpt.textContent = "[+ Custom Live Pytest Code]";
        sel.appendChild(customOpt);

        onFileSelected();
      } catch (err) {
        showAlert("Failed to load files: " + err, "error");
      }
    }

    function onFileSelected() {
      const sel = document.getElementById('fileDropdown');
      const editor = document.getElementById('codeEditor');
      const status = document.getElementById('editorStatus');
      const label = document.getElementById('editorLabel');

      if (sel.value === "__CUSTOM__") {
        label.textContent = "Custom Live Pytest Sandbox";
        status.textContent = "Editable";
        editor.readOnly = false;
        if (!editor.value || !editor.value.includes("def test_")) {
          editor.value = "import random\nimport os\n\nCACHE = {}\n\ndef test_custom_pollute():\n    CACHE['flag'] = True\n\ndef test_custom_consumer():\n    assert CACHE.get('flag') is True\n\ndef test_custom_unseeded():\n    vals = [random.random() for _ in range(10)]\n    assert sum(vals)/len(vals) > 0.42\n";
        }
      } else {
        label.textContent = sel.value;
        status.textContent = "Read-Only";
        editor.readOnly = true;
        editor.value = filesCache[sel.value] || "";
      }
    }

    function showAlert(msg, type) {
      const el = document.getElementById('statusAlert');
      el.className = "status-alert active " + type;
      el.innerHTML = msg;
    }

    function hideAlert() {
      document.getElementById('statusAlert').className = "status-alert";
    }

    async function runScan() {
      const sel = document.getElementById('fileDropdown');
      const editor = document.getElementById('codeEditor');
      const btn = document.getElementById('btnScan');

      btn.disabled = true;
      document.getElementById('btnPatch').disabled = true;
      document.getElementById('btnApply').disabled = true;
      showAlert("Running Forensic Scan across perturbation engine... please wait (~20-40s)", "loading");

      let payload = {};
      if (sel.value === "__CUSTOM__") {
        payload = { custom_code: editor.value };
      } else {
        payload = { file_path: sel.value };
      }

      try {
        const res = await fetch('/api/scan', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        btn.disabled = false;

        if (data.error) {
          showAlert("Scan error: " + data.error, "error");
          return;
        }

        currentReports = data.results;
        currentDiff = data.diff;

        showAlert(`Forensic scan complete in ${data.scan_time.toFixed(1)}s across ${data.subprocess_count} subprocess runs.`, "success");
        renderResults(data);

        document.getElementById('btnPatch').disabled = false;
        document.getElementById('btnApply').disabled = false;
        document.getElementById('btnRestore').disabled = false;
      } catch (err) {
        btn.disabled = false;
        showAlert("Scan failed: " + err, "error");
      }
    }

    function renderResults(data) {
      document.getElementById('metricsRow').style.display = "grid";
      document.getElementById('metricTime').textContent = data.scan_time.toFixed(1) + "s";
      document.getElementById('metricSubs').textContent = data.subprocess_count;
      document.getElementById('metricTests').textContent = data.results.length;

      let flakyCount = data.results.filter(r => r.verdict.startsWith("FLAKY") || r.verdict === "ORDER_DEPENDENT" || r.verdict === "POLLUTER").length;
      document.getElementById('metricCure').textContent = `${flakyCount} Flakes Found`;

      const section = document.getElementById('autopsySection');
      const container = document.getElementById('cardsContainer');
      section.style.display = "block";
      container.innerHTML = "";

      data.results.forEach(r => {
        const card = document.createElement('div');
        card.className = "test-card";

        let astHtml = "N/A";
        if (r.findings && r.findings.length > 0) {
          astHtml = r.findings.map(f => `
            <div><strong>L${f.line} [${f.category}]</strong></div>
            <div style="color: #9ca3af; margin-bottom: 4px;">${f.prescription}</div>
            <div class="snippet-box mono">${f.code_snippet}</div>
          `).join('<hr style="border: 0; border-top: 1px solid rgba(255,255,255,0.06); margin: 8px 0;">');
        }

        let culpritHtml = r.culprit ? `<div style="margin-top: 4px; color: #c084fc;"><strong>Culprit Predecessor:</strong> ${r.culprit}</div>` : "";
        let confHtml = r.confidence_runs !== null ? `${r.confidence_runs} Clean Runs` : "N/A";

        card.innerHTML = `
          <div class="test-card-header">
            <span class="test-name mono">${r.name}</span>
            <span class="badge badge-${r.verdict}">${r.verdict}</span>
          </div>
          <div class="test-body-grid">
            <div class="info-pane">
              <div class="info-label">Root Cause Analysis</div>
              <div class="info-val">${r.root_cause}</div>
              ${culpritHtml}
              <div style="margin-top: 10px; font-size: 11px; color: var(--text-dim);">
                Sweep Failure Rate: <span class="mono" style="color: white;">${(r.sweep_fail_rate * 100).toFixed(0)}%</span> |
                99% Conf. Metric: <span class="mono" style="color: #34d399;">${confHtml}</span>
              </div>
            </div>
            <div class="info-pane">
              <div class="info-label">AST X-Ray & Prescription</div>
              <div class="info-val">${astHtml}</div>
            </div>
          </div>
        `;
        container.appendChild(card);
      });
    }

    function previewPatch() {
      if (!currentDiff) {
        showAlert("No diff generated.", "error");
        return;
      }
      const section = document.getElementById('diffSection');
      section.style.display = "block";
      const viewer = document.getElementById('diffViewer');
      document.getElementById('afterFixContainer').style.display = "none";

      const lines = currentDiff.split('\n');
      const colored = lines.map(line => {
        if (line.startsWith('+') && !line.startsWith('+++')) return `<span class="diff-add">${escapeHtml(line)}</span>`;
        if (line.startsWith('-') && !line.startsWith('---')) return `<span class="diff-del">${escapeHtml(line)}</span>`;
        if (line.startsWith('@@')) return `<span class="diff-hunk">${escapeHtml(line)}</span>`;
        return escapeHtml(line);
      }).join('\n');

      viewer.innerHTML = colored;
      section.scrollIntoView({ behavior: 'smooth' });
    }

    async function applyFix() {
      const sel = document.getElementById('fileDropdown');
      const btn = document.getElementById('btnApply');
      btn.disabled = true;

      showAlert("Applying AST Patch and running closed-loop verification across all perturbation sweeps... (~30-50s)", "loading");

      try {
        const res = await fetch('/api/fix', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ file_path: sel.value, action: 'apply' })
        });
        const data = await res.json();
        btn.disabled = false;

        if (data.error) {
          showAlert("Apply error: " + data.error, "error");
          return;
        }

        showAlert(`Cure verified! ${data.healed} tests healed to STABLE. ${data.remaining_bugs} genuine bug remains.`, "success");

        // Display after table
        previewPatch();
        const afterCont = document.getElementById('afterFixContainer');
        afterCont.style.display = "block";
        const tbody = document.getElementById('afterFixBody');
        tbody.innerHTML = "";

        const afterMap = {};
        data.after.forEach(r => { afterMap[r.name] = r.verdict; });

        data.before.forEach(r => {
          const afterV = afterMap[r.name] || "UNKNOWN";
          const row = document.createElement('tr');
          row.innerHTML = `
            <td class="mono"><strong>${r.name}</strong></td>
            <td><span class="badge badge-${r.verdict}">${r.verdict}</span></td>
            <td><span class="badge badge-${afterV}">${afterV}</span></td>
          `;
          tbody.appendChild(row);
        });

        const bugStr = data.remaining_bugs === 1 ? "1 genuine bug remains" : `${data.remaining_bugs} genuine bugs remain`;
        document.getElementById('healSummary').textContent = `${data.healed} of ${data.before.length} tests healed, ${bugStr}`;
        afterCont.scrollIntoView({ behavior: 'smooth' });
      } catch (err) {
        btn.disabled = false;
        showAlert("Apply failed: " + err, "error");
      }
    }

    async function restoreOriginal() {
      const sel = document.getElementById('fileDropdown');
      const btn = document.getElementById('btnRestore');
      btn.disabled = true;

      try {
        const res = await fetch('/api/fix', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ file_path: sel.value, action: 'restore' })
        });
        const data = await res.json();
        btn.disabled = false;

        showAlert("File restored to original unpatched state.", "success");
        await loadFiles();
      } catch (err) {
        btn.disabled = false;
        showAlert("Restore failed: " + err, "error");
      }
    }

    function escapeHtml(str) {
      return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    window.onload = loadFiles;
  </script>
</body>
</html>
"""


def _get_all_test_files() -> List[Dict[str, str]]:
    """Discover all test files in demo_sick_repo/ and benchmark_suites/."""
    results = []
    base_dirs = [Path("demo_sick_repo"), Path("benchmark_suites")]
    for b in base_dirs:
        if b.exists():
            for p in sorted(b.glob("test_*.py")):
                try:
                    content = p.read_text(encoding="utf-8")
                    results.append({
                        "path": p.as_posix(),
                        "name": p.name,
                        "content": content,
                    })
                except Exception:
                    pass
    return results


class FlakeDoctorHandler(BaseHTTPRequestHandler):
    """HTTP Request Handler for Flake Doctor Web Console."""

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default stdout request logging for clean console."""
        return

    def _send_json(self, data: Any, status: int = 200) -> None:
        raw = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(raw)

    def _send_html(self, html_str: str) -> None:
        raw = html_str.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/" or parsed.path == "/index.html":
            self._send_html(HTML_DASHBOARD)
        elif parsed.path == "/api/files":
            files = _get_all_test_files()
            self._send_json({"files": files})
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
        try:
            req_data = json.loads(body)
        except json.JSONDecodeError:
            self._send_json({"error": "Invalid JSON"}, 400)
            return

        if parsed.path == "/api/scan":
            self._handle_scan(req_data)
        elif parsed.path == "/api/fix":
            self._handle_fix(req_data)
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

    def _handle_scan(self, req_data: Dict[str, Any]) -> None:
        custom_code = req_data.get("custom_code")
        file_path_str = req_data.get("file_path")

        if custom_code is not None:
            target_file = Path("benchmark_suites") / "_judge_custom_live.py"
            target_file.parent.mkdir(exist_ok=True)
            target_file.write_text(custom_code, encoding="utf-8")
        elif file_path_str:
            target_file = Path(file_path_str)
        else:
            self._send_json({"error": "Missing file_path or custom_code"}, 400)
            return

        if not target_file.exists():
            self._send_json({"error": f"File not found: {target_file}"}, 404)
            return

        t0 = time.monotonic()
        try:
            reports = diagnose(target_file)
            _, diff = build_patch(target_file, reports)
            elapsed = time.monotonic() - t0
            sub_count = getattr(reports[0], "_subprocess_count", 0) if reports else 0

            self._send_json({
                "results": [r.to_dict() for r in reports],
                "diff": diff,
                "file_path": target_file.as_posix(),
                "scan_time": elapsed,
                "subprocess_count": sub_count,
            })
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_fix(self, req_data: Dict[str, Any]) -> None:
        file_path_str = req_data.get("file_path")
        action = req_data.get("action", "apply")

        if not file_path_str:
            self._send_json({"error": "Missing file_path"}, 400)
            return

        target_file = Path(file_path_str)
        bak_file = target_file.with_name(target_file.name + ".bak")

        if action == "restore":
            if bak_file.exists():
                shutil.copy2(bak_file, target_file)
                bak_file.unlink(missing_ok=True)
            self._send_json({"status": "restored"})
            return

        if action == "apply":
            if not target_file.exists():
                self._send_json({"error": f"File not found: {target_file}"}, 404)
                return

            try:
                # 1. Diagnose before
                before_reports = diagnose(target_file)
                # 2. Build patch
                patched_src, diff = build_patch(target_file, before_reports)

                # 3. Backup original if not already backed up
                if not bak_file.exists():
                    shutil.copy2(target_file, bak_file)

                # 4. Write patched code to target file
                target_file.write_text(patched_src, encoding="utf-8")

                # 5. Diagnose after
                after_reports = diagnose(target_file)

                # Count healed
                after_map = {r.name: r for r in after_reports}
                healed = 0
                for b in before_reports:
                    aft = after_map.get(b.name)
                    if aft and b.verdict != aft.verdict and aft.verdict == "STABLE":
                        healed += 1

                remaining_bugs = sum(1 for r in after_reports if r.verdict == "BROKEN_BUILD")

                self._send_json({
                    "status": "applied",
                    "before": [r.to_dict() for r in before_reports],
                    "after": [r.to_dict() for r in after_reports],
                    "diff": diff,
                    "healed": healed,
                    "remaining_bugs": remaining_bugs,
                })
            except Exception as e:
                self._send_json({"error": str(e)}, 500)


def run_server(port: int = 8080) -> None:
    """Launch the Flake Doctor Web Server."""
    server_address = ("", port)
    httpd = ThreadingHTTPServer(server_address, FlakeDoctorHandler)
    print(f"Flake Doctor Web Console running at http://127.0.0.1:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down Flake Doctor Web Console.")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    run_server(8080)
