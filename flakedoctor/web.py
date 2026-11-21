"""Flake Doctor Live Local Web Dashboard.

Zero external dependencies - built entirely on Python standard library http.server.
Light-mode warm peach/cream/sage editorial UI.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import shutil
import tempfile
import threading
import time
import urllib.parse
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional

from .ast_analyzer import analyze_test
from .engine import TestReport, diagnose
from .patcher import build_patch, verify_fix

try:
    from .engine import ENGINE_VERSION
except ImportError:
    ENGINE_VERSION = "1.0.0"


HTML_PAGE_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>__PAGE_TITLE__</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=JetBrains+Mono:wght@400;500&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      background: linear-gradient(160deg, #F7DFD2 0%, #F5ECE3 45%, #E8EEE9 100%);
      color: #1C1917;
      margin: 0;
      padding: 24px 32px 64px;
      min-height: 100vh;
      font-family: 'Plus Jakarta Sans', -apple-system, 'Segoe UI', sans-serif;
      line-height: 1.5;
      -webkit-font-smoothing: antialiased;
    }

    code, pre, .mono {
      font-family: 'JetBrains Mono', Consolas, monospace;
    }

    /* Floating Pill Navbar */
    .pill-navbar {
      max-width: 1220px;
      margin: 0 auto 44px;
      background: rgba(252, 250, 247, 0.92);
      border-radius: 9999px;
      padding: 12px 24px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      box-shadow: 0 6px 24px rgba(28, 25, 23, 0.05);
      border: 1px solid rgba(255, 255, 255, 0.85);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
    }

    .nav-left {
      display: flex;
      align-items: center;
      gap: 10px;
    }

    .nav-dot {
      width: 9px;
      height: 9px;
      border-radius: 50%;
      background: #22C55E;
      display: inline-block;
      box-shadow: 0 0 8px rgba(34, 197, 94, 0.4);
    }

    .nav-brand-title {
      font-size: 0.78rem;
      letter-spacing: 0.1em;
      font-weight: 700;
      color: #1C1917;
      text-transform: uppercase;
    }

    .nav-tabs {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .nav-tab {
      border-radius: 9999px;
      padding: 7px 18px;
      font-size: 0.85rem;
      font-weight: 500;
      text-decoration: none;
      color: #57534E;
      transition: all 0.15s ease;
      cursor: pointer;
    }

    .nav-tab:hover {
      color: #1C1917;
    }

    .nav-tab.active-tab {
      background: #F2EDE4;
      font-weight: 600;
      color: #1C1917;
    }

    .nav-right {
      display: flex;
      align-items: center;
    }

    .nav-team-label {
      font-size: 0.7rem;
      letter-spacing: 0.1em;
      color: #78716C;
      font-weight: 600;
      text-transform: uppercase;
    }

    .nav-team-name {
      font-weight: 700;
      font-size: 0.84rem;
      color: #1C1917;
      margin-left: 4px;
      margin-right: 10px;
    }

    .nav-ps-badge {
      background: #F2EDE4;
      border: 1px solid #E5DFD5;
      color: #57534E;
      font-size: 0.72rem;
      font-weight: 600;
      padding: 4px 10px;
      border-radius: 9999px;
    }

    /* Hero Grid */
    .hero-grid {
      max-width: 1220px;
      margin: 0 auto 32px;
      display: grid;
      grid-template-columns: 1.15fr 0.85fr;
      gap: 36px;
      align-items: start;
    }

    .hero-kicker {
      font-size: 0.72rem;
      letter-spacing: 0.14em;
      color: #78716C;
      font-weight: 600;
      text-transform: uppercase;
      margin-bottom: 12px;
    }

    .hero-title {
      font-family: 'Instrument Serif', Georgia, serif;
      font-size: clamp(2.6rem, 5vw, 4.4rem);
      line-height: 1.02;
      font-weight: 400;
      margin: 0 0 18px;
      color: #1C1917;
    }

    .hero-title em {
      font-style: italic;
      color: #92400E;
    }

    .hero-subtitle {
      color: #57534E;
      font-size: 1.05rem;
      line-height: 1.6;
      max-width: 520px;
      margin-bottom: 24px;
    }

    .hero-meta-row {
      display: flex;
      gap: 36px;
    }

    .meta-item-label {
      font-size: 0.72rem;
      letter-spacing: 0.12em;
      color: #78716C;
      font-weight: 600;
      text-transform: uppercase;
      margin-bottom: 4px;
    }

    .meta-item-val {
      font-weight: 600;
      font-size: 0.92rem;
      color: #1C1917;
    }

    /* Target Suite Control Card */
    .control-card {
      background: #FCFBF9;
      border-radius: 26px;
      padding: 28px;
      box-shadow: 0 12px 32px rgba(28, 25, 23, 0.045);
      border: 1px solid rgba(28, 25, 23, 0.06);
    }

    .control-top-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 10px;
    }

    .control-kicker {
      font-size: 0.72rem;
      letter-spacing: 0.12em;
      color: #78716C;
      font-weight: 600;
      text-transform: uppercase;
    }

    .files-badge {
      background: #F2EDE4;
      border: 1px solid #E5DFD5;
      color: #57534E;
      font-size: 0.72rem;
      font-weight: 600;
      padding: 3px 10px;
      border-radius: 9999px;
    }

    .suite-select {
      background: #F5F1EA;
      border: 1px solid #E5DFD5;
      border-radius: 14px;
      padding: 12px 14px;
      width: 100%;
      font-weight: 500;
      font-family: 'Plus Jakarta Sans', -apple-system, 'Segoe UI', sans-serif;
      font-size: 0.88rem;
      color: #1C1917;
      outline: none;
      margin-top: 6px;
      margin-bottom: 10px;
      box-sizing: border-box;
      transition: border-color 0.15s ease;
    }

    .suite-select:focus {
      border-color: #78716C;
    }

    .toggle-editor-link {
      font-size: 0.8rem;
      font-weight: 600;
      color: #57534E;
      text-decoration: underline;
      display: inline-block;
      margin-bottom: 12px;
      cursor: pointer;
    }

    .toggle-editor-link:hover {
      color: #1C1917;
    }

    .code-box {
      background: #F7F4EE;
      border: 1px solid #E6E0D6;
      border-radius: 16px;
      color: #292524;
      font-family: 'JetBrains Mono', Consolas, monospace;
      font-size: 0.82rem;
      padding: 14px;
      height: 150px;
      width: 100%;
      box-sizing: border-box;
      resize: vertical;
      outline: none;
      line-height: 1.45;
      margin-bottom: 16px;
      display: block;
    }

    .code-box:focus {
      border-color: #78716C;
    }

    .btn-row {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
    }

    .btn-primary {
      background: #1E293B;
      color: #FFFFFF;
      border-radius: 9999px;
      padding: 11px 22px;
      font-weight: 600;
      border: none;
      cursor: pointer;
      font-family: 'Plus Jakarta Sans', sans-serif;
      font-size: 0.84rem;
      display: inline-flex;
      align-items: center;
      gap: 8px;
      transition: opacity 0.15s ease;
    }

    .btn-primary:hover {
      opacity: 0.92;
    }

    .btn-secondary {
      background: #F2EDE4;
      color: #1C1917;
      border-radius: 9999px;
      padding: 10px 16px;
      font-weight: 600;
      border: 1px solid #E5DFD5;
      cursor: pointer;
      font-family: 'Plus Jakarta Sans', sans-serif;
      font-size: 0.84rem;
      transition: background 0.15s ease;
    }

    .btn-secondary:hover {
      background: #E8E2D7;
    }

    .btn-primary:disabled, .btn-secondary:disabled {
      opacity: 0.55;
      cursor: not-allowed;
    }

    /* Bento Summary Row */
    .bento-row {
      max-width: 1220px;
      margin: 0 auto 32px;
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 22px;
    }

    .bento-card {
      border-radius: 24px;
      padding: 26px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      min-height: 140px;
    }

    .bento-card-1 {
      background: #1E293B;
      color: #FFFFFF;
      border: 1px solid rgba(255, 255, 255, 0.08);
    }

    .bento-card-2 {
      background: #F5EBDD;
      color: #1C1917;
      border: 1px solid rgba(28, 25, 23, 0.06);
    }

    .bento-card-3 {
      background: #E5EFE9;
      color: #1C1917;
      border: 1px solid rgba(28, 25, 23, 0.06);
    }

    .bento-kicker-1 {
      font-size: 0.72rem;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: #94A3B8;
      font-weight: 600;
      margin-bottom: 8px;
    }

    .bento-kicker {
      font-size: 0.72rem;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: #78716C;
      font-weight: 600;
      margin-bottom: 8px;
    }

    .bento-number {
      font-family: 'Instrument Serif', Georgia, serif;
      font-size: 3.2rem;
      line-height: 1;
      margin-bottom: 8px;
    }

    .bento-number-2 {
      color: #92400E;
    }

    .bento-status-text {
      font-size: 1.45rem;
      font-weight: 700;
      line-height: 1.2;
      margin-bottom: 8px;
      color: #14532D;
      min-height: 2.2rem;
      display: flex;
      align-items: center;
    }

    .bento-footer-1 {
      font-size: 0.82rem;
      color: #94A3B8;
    }

    .bento-footer {
      font-size: 0.82rem;
      color: #57534E;
    }

    /* Autopsy Card */
    .autopsy-card {
      max-width: 1220px;
      margin: 0 auto 32px;
      background: #FCFBF9;
      border-radius: 26px;
      padding: 8px 28px;
      box-shadow: 0 12px 32px rgba(28, 25, 23, 0.04);
      border: 1px solid rgba(28, 25, 23, 0.06);
    }

    .autopsy-empty-state {
      padding: 56px 16px;
      text-align: center;
      color: #78716C;
      font-size: 0.95rem;
    }

    .autopsy-row {
      display: grid;
      grid-template-columns: 160px 1fr auto;
      gap: 20px;
      align-items: center;
      padding: 22px 0;
      border-bottom: 1px solid #ECE7DF;
    }

    .autopsy-row:last-child {
      border-bottom: none;
    }

    .col-confidence-clean {
      font-weight: 700;
      font-size: 0.9rem;
      color: #1C1917;
      margin-bottom: 2px;
    }

    .col-confidence-fail {
      font-size: 0.78rem;
      color: #78716C;
    }

    .col-test-name {
      font-family: 'JetBrains Mono', Consolas, monospace;
      font-size: 0.92rem;
      font-weight: 700;
      color: #1C1917;
      margin-bottom: 4px;
    }

    .col-root-cause {
      color: #57534E;
      font-size: 0.85rem;
      line-height: 1.4;
      margin-bottom: 6px;
    }

    .culprit-tag {
      background: #FEF3C7;
      color: #92400E;
      border: 1px solid #FDE68A;
      padding: 2px 8px;
      border-radius: 6px;
      font-size: 0.75rem;
      font-family: 'JetBrains Mono', Consolas, monospace;
      font-weight: 600;
      display: inline-block;
      margin-bottom: 6px;
    }

    .ast-prescription-box {
      background: #F6F3EC;
      border-left: 3px solid #D97706;
      padding: 8px 12px;
      border-radius: 8px;
      font-family: 'JetBrains Mono', Consolas, monospace;
      font-size: 0.8rem;
      color: #292524;
      line-height: 1.4;
      margin-top: 4px;
    }

    /* Verdict Pills */
    .verdict-pill {
      padding: 6px 14px;
      border-radius: 9999px;
      font-weight: 700;
      font-size: 0.76rem;
      letter-spacing: 0.03em;
      white-space: nowrap;
      display: inline-block;
    }

    .pill-polluter {
      background: #FEF3C7;
      color: #92400E;
      border: 1px solid #FDE68A;
    }

    .pill-order {
      background: #F3E8FF;
      color: #6B21A8;
      border: 1px solid #E9D5FF;
    }

    .pill-flaky {
      background: #FFEDD5;
      color: #9A3412;
      border: 1px solid #FED7AA;
    }

    .pill-broken {
      background: #FEE2E2;
      color: #991B1B;
      border: 1px solid #FECACA;
    }

    .pill-stable {
      background: #DCFCE7;
      color: #166534;
      border: 1px solid #BBF7D0;
    }

    /* Diff and After-Fix Drawer */
    .drawer-section {
      max-width: 1220px;
      margin: 0 auto 32px;
      background: #FCFBF9;
      border-radius: 26px;
      padding: 28px;
      box-shadow: 0 12px 32px rgba(28, 25, 23, 0.04);
      border: 1px solid rgba(28, 25, 23, 0.06);
    }

    .drawer-placeholder {
      color: #78716C;
      font-size: 0.9rem;
      padding: 8px 0;
    }

    .diff-box {
      background: #FDFDFD;
      border: 1px solid #E5DFD5;
      border-radius: 14px;
      padding: 16px;
      font-family: 'JetBrains Mono', Consolas, monospace;
      font-size: 0.8rem;
      line-height: 1.5;
      overflow-x: auto;
      max-height: 380px;
      margin-top: 14px;
    }

    .diff-add {
      background: #ECFDF5;
      color: #065F46;
      display: block;
      padding: 1px 6px;
      border-radius: 2px;
    }

    .diff-del {
      background: #FEF2F2;
      color: #991B1B;
      display: block;
      padding: 1px 6px;
      border-radius: 2px;
    }

    .diff-hdr {
      color: #475569;
      font-weight: 600;
      display: block;
      padding: 1px 6px;
    }

    .compare-table {
      width: 100%;
      border-collapse: collapse;
      margin-top: 18px;
      font-size: 0.84rem;
    }

    .compare-table th {
      text-align: left;
      font-size: 0.72rem;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: #78716C;
      padding: 8px 12px;
      border-bottom: 1px solid #E5DFD5;
    }

    .compare-table td {
      padding: 10px 12px;
      border-bottom: 1px solid #F0EAE1;
    }

    /* How It Works Section */
    .how-it-works-card {
      max-width: 1220px;
      margin: 0 auto;
      background: #FCFBF9;
      border-radius: 26px;
      padding: 28px;
      box-shadow: 0 12px 32px rgba(28, 25, 23, 0.04);
      border: 1px solid rgba(28, 25, 23, 0.06);
    }

    .detector-line {
      font-size: 0.86rem;
      color: #57534E;
      line-height: 1.6;
      margin-bottom: 8px;
    }

    .detector-line strong {
      color: #1C1917;
    }

    .formula-badge {
      background: #F5EBDD;
      border: 1px solid #EAE0D1;
      padding: 8px 14px;
      border-radius: 8px;
      font-family: 'JetBrains Mono', Consolas, monospace;
      font-size: 0.82rem;
      color: #92400E;
      display: inline-block;
      margin-top: 12px;
      margin-bottom: 10px;
    }

    .formula-note {
      font-size: 0.78rem;
      color: #78716C;
      font-style: italic;
    }

    /* Responsive */
    @media (max-width: 960px) {
      .pill-navbar {
        flex-wrap: wrap;
        gap: 12px;
        border-radius: 20px;
      }
      .hero-grid {
        grid-template-columns: 1fr;
      }
      .bento-row {
        grid-template-columns: 1fr;
      }
      .autopsy-row {
        grid-template-columns: 1fr;
        gap: 12px;
      }
    }
  </style>
</head>
<body>

  <!-- Floating Pill Navbar -->
  <nav class="pill-navbar">
    <div class="nav-left">
      <span class="nav-dot"></span>
      <span class="nav-brand-title">FLAKE DOCTOR</span>
    </div>
    <div class="nav-tabs">
      <a href="#section-diagnostics" id="tab-diagnostics" class="nav-tab active-tab">Diagnostics</a>
      <a href="#section-patcher" id="tab-patcher" class="nav-tab">AST Patcher</a>
      <a href="#section-how-it-works" id="tab-how-it-works" class="nav-tab">How It Works</a>
    </div>
    <div class="nav-right">
      <span class="nav-team-label">TEAM</span>
      <span class="nav-team-name">DUST_BUSTERS</span>
      <span class="nav-ps-badge">PS ID: OI</span>
    </div>
  </nav>

  <!-- Hero Grid (Diagnostics Section) -->
  <section class="hero-grid" id="section-diagnostics">
    <div>
      <div class="hero-kicker">FORENSIC TEST DIAGNOSTICS</div>
      <h1 class="hero-title">Diagnose, isolate, and <em>heal.</em></h1>
      <p class="hero-subtitle">
        Root-cause analysis, binary order bisection, and closed-loop AST auto-patching for non-deterministic Python test suites.
      </p>
      <div class="hero-meta-row">
        <div>
          <div class="meta-item-label">ENGINE</div>
          <div class="meta-item-val">AST + 5-phase forensic scan</div>
        </div>
        <div>
          <div class="meta-item-label">CONFIDENCE</div>
          <div class="meta-item-val">Est. 99% (sweep-based)</div>
        </div>
      </div>
    </div>

    <!-- Right: Target Suite Control Card -->
    <div class="control-card">
      <div class="control-top-row">
        <div class="control-kicker">TARGET TEST SUITE</div>
        <div id="filesCountBadge" class="files-badge">0 FILES READY</div>
      </div>

      <select id="suiteSelect" class="suite-select">
        <option value="">Loading test suites...</option>
      </select>

      <a href="#" id="toggleEditorLink" class="toggle-editor-link">Switch to Custom Live Code Editor</a>

      <textarea id="customCodeArea" class="code-box" placeholder="# Paste or inspect pytest code here..."></textarea>
      <div id="customCodeWarning" style="font-size: 0.75rem; color: #6B7280; margin-top: 4px; display: none;">Custom code runs on this machine. Local use only.</div>

      <div class="btn-row">
        <button id="btnScan" class="btn-primary">
          <span id="scanBtnLabel">Run Forensic Scan</span>
        </button>
        <button id="btnPreviewPatch" class="btn-secondary">Preview AST Patch</button>
        <button id="btnApplyFix" class="btn-secondary">Apply Fix & Verify</button>
        <button id="btnRestore" class="btn-secondary">Restore</button>
      </div>
    </div>
  </section>

  <!-- Bento Summary Row -->
  <section class="bento-row">
    <!-- Card 1 -->
    <div class="bento-card bento-card-1" id="card1Bento">
      <div>
        <div class="bento-kicker-1">TOTAL RUNS EXECUTED</div>
        <div id="card1TotalRuns" class="bento-number">0</div>
      </div>
      <div class="bento-footer-1">Across the 5 scan phases</div>
    </div>

    <!-- Card 2 -->
    <div class="bento-card bento-card-2">
      <div>
        <div class="bento-kicker">FLAKES & POLLUTERS</div>
        <div id="card2FlakesCount" class="bento-number bento-number-2">0</div>
      </div>
      <div class="bento-footer">Isolated with AST line pointers</div>
    </div>

    <!-- Card 3 -->
    <div class="bento-card bento-card-3">
      <div>
        <div class="bento-kicker">VERIFICATION STATUS</div>
        <div id="card3StatusText" class="bento-status-text">Ready</div>
      </div>
      <div class="bento-footer">Closed-loop, estimate-based</div>
    </div>
  </section>

  <!-- Autopsy Card -->
  <section class="autopsy-card">
    <div id="autopsyEmptyState" class="autopsy-empty-state">
      No scan yet. Pick a suite and run a forensic scan.
    </div>
    <div id="autopsyRowsContainer"></div>
  </section>

  <!-- AST Patcher & Verification Drawer -->
  <section class="drawer-section" id="section-patcher">
    <div class="hero-kicker">AST AUTO-PATCHER</div>
    <div id="patcherContentArea">
      <div class="drawer-placeholder">Run a scan, then click Preview AST Patch</div>
    </div>
  </section>

  <!-- How It Works Section -->
  <section class="how-it-works-card" id="section-how-it-works">
    <div class="hero-kicker">METHODOLOGY</div>
    <h3 style="font-size: 1.25rem; font-weight: 700; color: #1C1917; margin-bottom: 14px;">How It Works</h3>
    
    <div class="detector-line">
      <strong>1. Order / State Bisect:</strong> Identifies state polluters and order-dependent consumers via binary permutation bisecting.
    </div>
    <div class="detector-line">
      <strong>2. Seed Sweep:</strong> Evaluates unseeded PRNG randomness across varying seeds to isolate threshold flakiness.
    </div>
    <div class="detector-line">
      <strong>3. Schedule-Stress Sweep:</strong> Injects thread contention and CPU jitter to surface latent timing races.
    </div>
    <div class="detector-line">
      <strong>4. Regression Separation:</strong> Distinguishes genuine deterministic build failures from non-deterministic flakes.
    </div>

    <div>
      <div class="formula-badge">N = ceil(ln(0.01) / ln(1 - p))</div>
    </div>
    <div class="formula-note">
      Rates and clean-run bounds are statistical estimates derived from a designed sweep matrix.
    </div>
  </section>

  <script>
    let currentFiles = [];
    let lastScanData = null;
    let timerInterval = null;
    let secondsElapsed = 0;

    function escapeHtml(str) {
      if (!str) return '';
      return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
    }

    // Tab navigation switching
    document.querySelectorAll('.nav-tab').forEach(tab => {
      tab.addEventListener('click', (e) => {
        document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active-tab'));
        tab.classList.add('active-tab');
      });
    });

    // Editor permissions and toggle
    const allowCustomCode = __ALLOW_CUSTOM_CODE__;
    const toggleEditorLink = document.getElementById('toggleEditorLink');
    const customCodeArea = document.getElementById('customCodeArea');
    const customCodeWarning = document.getElementById('customCodeWarning');
    const suiteSelect = document.getElementById('suiteSelect');
    let isEditorVisible = allowCustomCode;

    if (!allowCustomCode) {
      if (toggleEditorLink) toggleEditorLink.style.display = 'none';
      if (customCodeArea) customCodeArea.style.display = 'none';
      if (customCodeWarning) customCodeWarning.style.display = 'none';
    } else {
      if (customCodeWarning) customCodeWarning.style.display = 'block';
      toggleEditorLink.addEventListener('click', (e) => {
        e.preventDefault();
        isEditorVisible = !isEditorVisible;
        if (isEditorVisible) {
          customCodeArea.style.display = 'block';
          toggleEditorLink.textContent = 'Hide Custom Live Code Editor';
        } else {
          customCodeArea.style.display = 'none';
          toggleEditorLink.textContent = 'Switch to Custom Live Code Editor';
        }
      });
    }

    // Load available files on startup
    async function loadFiles() {
      try {
        const res = await fetch('/api/files');
        const data = await res.json();
        currentFiles = data.files || [];
        
        const countBadge = document.getElementById('filesCountBadge');
        countBadge.textContent = `${currentFiles.length} FILES READY`;

        suiteSelect.innerHTML = '';
        currentFiles.forEach((f, idx) => {
          const opt = document.createElement('option');
          opt.value = f.path;
          opt.textContent = `${f.name} (${f.path.split('/')[0]})`;
          if (idx === 0) opt.selected = true;
          suiteSelect.appendChild(opt);
        });

        if (currentFiles.length > 0) {
          customCodeArea.value = currentFiles[0].content;
        }
      } catch (err) {
        console.error('Failed to load files:', err);
      }
    }

    suiteSelect.addEventListener('change', (e) => {
      const selected = currentFiles.find(f => f.path === e.target.value);
      if (selected) {
        customCodeArea.value = selected.content;
      }
    });

    function setButtonsDisabled(disabled) {
      document.getElementById('btnScan').disabled = disabled;
      document.getElementById('btnPreviewPatch').disabled = disabled;
      document.getElementById('btnApplyFix').disabled = disabled;
      document.getElementById('btnRestore').disabled = disabled;
    }

    function startTimer(actionLabel) {
      secondsElapsed = 0;
      const statusText = document.getElementById('card3StatusText');
      statusText.style.color = '#92400E';
      statusText.textContent = `${actionLabel} (0s)`;
      
      clearInterval(timerInterval);
      timerInterval = setInterval(() => {
        secondsElapsed++;
        statusText.textContent = `${actionLabel} (${secondsElapsed}s)`;
      }, 1000);
    }

    function stopTimer() {
      clearInterval(timerInterval);
    }

    function getVerdictPill(verdict) {
      const pill = document.createElement('span');
      pill.className = 'verdict-pill';
      pill.textContent = verdict || 'UNKNOWN';

      switch (verdict) {
        case 'POLLUTER':
          pill.classList.add('pill-polluter');
          break;
        case 'ORDER_DEPENDENT':
          pill.classList.add('pill-order');
          break;
        case 'FLAKY_PRNG':
        case 'FLAKY_TIMING':
          pill.classList.add('pill-flaky');
          break;
        case 'BROKEN_BUILD':
          pill.classList.add('pill-broken');
          break;
        case 'STABLE':
        default:
          pill.classList.add('pill-stable');
          break;
      }
      return pill;
    }

    // Run Forensic Scan
    async function runScan() {
      setButtonsDisabled(true);
      const scanBtnLabel = document.getElementById('scanBtnLabel');
      scanBtnLabel.textContent = 'Scanning...';
      startTimer('Scanning...');

      try {
        const payload = {};
        const selectedPath = suiteSelect.value;
        const matching = currentFiles.find(f => f.path === selectedPath);

        if (!allowCustomCode || (matching && matching.content.trim() === customCodeArea.value.trim())) {
          payload.file_path = selectedPath;
        } else {
          payload.custom_code = customCodeArea.value;
        }

        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 300000);

        const res = await fetch('/api/scan', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
          signal: controller.signal
        });
        clearTimeout(timeoutId);

        let data = await res.json();

        if (data.error) {
          stopTimer();
          const statusText = document.getElementById('card3StatusText');
          statusText.style.color = '#991B1B';
          statusText.textContent = `Error: ${data.error}`;
          return;
        }

        if (data.status === 'running' && data.job_id) {
          const jobId = data.job_id;
          while (true) {
            await new Promise(r => setTimeout(r, 1000));
            const pollRes = await fetch('/api/scan/' + jobId);
            const pollData = await pollRes.json();
            if (pollData.progress) {
              const statusText = document.getElementById('card3StatusText');
              statusText.textContent = `Step ${pollData.progress.step}/5: ${pollData.progress.phase} (${secondsElapsed}s)`;
            }
            if (pollData.status === 'done') {
              data = pollData;
              break;
            } else if (pollData.status === 'error') {
              throw new Error(pollData.error || 'Scan failed');
            }
          }
        }
        stopTimer();

        lastScanData = data;
        renderScanResults(data);

        const statusText = document.getElementById('card3StatusText');
        statusText.style.color = '#14532D';
        if (data.cached) {
          statusText.textContent = 'Autopsy Ready (Cached)';
        } else {
          statusText.textContent = 'Autopsy Ready';
        }
      } catch (err) {
        stopTimer();
        const statusText = document.getElementById('card3StatusText');
        statusText.style.color = '#991B1B';
        statusText.textContent = `Error: ${err.message}`;
      } finally {
        setButtonsDisabled(false);
        scanBtnLabel.textContent = 'Run Forensic Scan';
      }
    }

    function renderScanResults(data) {
      const results = data.results || [];
      const emptyState = document.getElementById('autopsyEmptyState');
      const container = document.getElementById('autopsyRowsContainer');
      container.innerHTML = '';

      if (results.length === 0) {
        emptyState.style.display = 'block';
        emptyState.textContent = 'No tests found in target file.';
        return;
      }
      emptyState.style.display = 'none';

      let flakesCount = 0;
      let totalRuns = data.subprocess_count || 0;

      results.forEach(r => {
        if (r.verdict !== 'STABLE' && r.verdict !== 'BROKEN_BUILD') {
          flakesCount++;
        }

        const row = document.createElement('div');
        row.className = 'autopsy-row';

        // Left: Confidence
        const colLeft = document.createElement('div');
        const cleanEl = document.createElement('div');
        cleanEl.className = 'col-confidence-clean';

        const confRuns = (r.conservative_clean_runs !== undefined && r.conservative_clean_runs !== null)
          ? r.conservative_clean_runs
          : ((r.confidence_runs !== undefined && r.confidence_runs !== null) 
            ? r.confidence_runs 
            : r.est_clean_runs_99);

        if (r.verdict === 'ORDER_DEPENDENT') {
          cleanEl.textContent = 'Deterministic';
        } else if (r.verdict === 'STABLE' || r.verdict === 'BROKEN_BUILD') {
          cleanEl.textContent = '-';
        } else if (confRuns !== undefined && confRuns !== null) {
          cleanEl.textContent = `${confRuns} clean runs (99%, cons.)`;
        } else {
          cleanEl.textContent = '-';
        }

        const failEl = document.createElement('div');
        failEl.className = 'col-confidence-fail';
        const failRate = r.sweep_fail_rate !== undefined ? (r.sweep_fail_rate * 100).toFixed(0) : '0';
        if (r.ci_low !== undefined && r.ci_high !== undefined && r.verdict !== 'STABLE' && r.verdict !== 'BROKEN_BUILD' && r.verdict !== 'ORDER_DEPENDENT') {
          const lowPct = (r.ci_low * 100).toFixed(0);
          const highPct = (r.ci_high * 100).toFixed(0);
          failEl.textContent = `${failRate}% fail (95% CI ${lowPct}%-${highPct}%)`;
        } else {
          failEl.textContent = `${failRate}% fail (est.)`;
        }

        colLeft.appendChild(cleanEl);
        colLeft.appendChild(failEl);

        // Middle: Test info, root cause, culprit, AST
        const colMid = document.createElement('div');
        const nameEl = document.createElement('div');
        nameEl.className = 'col-test-name';
        nameEl.textContent = r.name || '';
        colMid.appendChild(nameEl);

        const causeEl = document.createElement('div');
        causeEl.className = 'col-root-cause';
        causeEl.textContent = r.root_cause || '';
        colMid.appendChild(causeEl);

        const culpritName = r.culprit || r.culprit_predecessor;
        if (culpritName) {
          const culpritEl = document.createElement('div');
          culpritEl.className = 'culprit-tag';
          culpritEl.textContent = `Culprit: ${culpritName}`;
          colMid.appendChild(culpritEl);
        }

        // AST prescription
        const findings = r.findings || [];
        if (findings.length > 0) {
          const astBox = document.createElement('div');
          astBox.className = 'ast-prescription-box';
          
          findings.forEach((f, fIdx) => {
            const fItem = document.createElement('div');
            let prefix = '';
            if (r.verdict === 'ORDER_DEPENDENT' && culpritName) {
              prefix = `(in culprit ${culpritName}) `;
            }
            fItem.textContent = `${prefix}L${f.line} [${f.category}]: ${f.prescription}`;
            if (fIdx > 0) {
              fItem.style.marginTop = '4px';
              fItem.style.borderTop = '1px dashed #E5DFD5';
              fItem.style.paddingTop = '4px';
            }
            astBox.appendChild(fItem);
          });
          colMid.appendChild(astBox);
        } else if (r.code_prescription) {
          const astBox = document.createElement('div');
          astBox.className = 'ast-prescription-box';
          let prefix = (r.verdict === 'ORDER_DEPENDENT' && culpritName) ? `(in culprit ${culpritName}) ` : '';
          const lineStr = r.ast_line ? `L${r.ast_line}: ` : '';
          astBox.textContent = `${prefix}${lineStr}${r.code_prescription}`;
          colMid.appendChild(astBox);
        }

        // Right: Verdict Pill
        const colRight = document.createElement('div');
        colRight.appendChild(getVerdictPill(r.verdict));

        row.appendChild(colLeft);
        row.appendChild(colMid);
        row.appendChild(colRight);
        container.appendChild(row);
      });

      // Update Bento numbers
      document.getElementById('card1TotalRuns').textContent = totalRuns;
      document.getElementById('card2FlakesCount').textContent = flakesCount;
    }

    function renderDiffBox(rawDiff) {
      const area = document.getElementById('patcherContentArea');
      area.innerHTML = '';

      if (!rawDiff || rawDiff.trim() === '') {
        const ph = document.createElement('div');
        ph.className = 'drawer-placeholder';
        ph.textContent = 'No patch changes required for this file.';
        area.appendChild(ph);
        return;
      }

      const pre = document.createElement('pre');
      pre.className = 'diff-box';

      const lines = rawDiff.split('\n');
      lines.forEach(line => {
        const span = document.createElement('span');
        span.textContent = line;
        if (line.startsWith('+') && !line.startsWith('+++')) {
          span.className = 'diff-add';
        } else if (line.startsWith('-') && !line.startsWith('---')) {
          span.className = 'diff-del';
        } else if (line.startsWith('@@') || line.startsWith('---') || line.startsWith('+++')) {
          span.className = 'diff-hdr';
        }
        pre.appendChild(span);
        pre.appendChild(document.createTextNode('\n'));
      });

      area.appendChild(pre);
    }

    // Preview AST Patch
    document.getElementById('btnPreviewPatch').addEventListener('click', () => {
      const targetSec = document.getElementById('section-patcher');
      if (lastScanData && lastScanData.diff) {
        renderDiffBox(lastScanData.diff);
      } else {
        const area = document.getElementById('patcherContentArea');
        area.innerHTML = '';
        const ph = document.createElement('div');
        ph.className = 'drawer-placeholder';
        ph.textContent = 'Run a scan, then click Preview AST Patch';
        area.appendChild(ph);
      }
      targetSec.scrollIntoView({ behavior: 'smooth' });
    });

    // Apply Fix & Verify
    async function applyFix() {
      const targetPath = lastScanData ? lastScanData.file_path : suiteSelect.value;
      if (!targetPath) {
        alert('Please select or scan a target file first.');
        return;
      }

      setButtonsDisabled(true);
      startTimer('Applying fix...');

      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 300000);

        const res = await fetch('/api/fix', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ file_path: targetPath, action: 'apply' }),
          signal: controller.signal
        });
        clearTimeout(timeoutId);

        const data = await res.json();
        stopTimer();

        if (data.error) {
          const statusText = document.getElementById('card3StatusText');
          statusText.style.color = '#991B1B';
          statusText.textContent = `Error: ${data.error}`;
          return;
        }

        // Update Card 3 Status
        const totalAfter = (data.after || []).length;
        const healedCount = data.healed || 0;
        const statusText = document.getElementById('card3StatusText');
        statusText.style.color = '#14532D';
        statusText.textContent = `Verified: ${healedCount} of ${totalAfter} healed`;

        // Render Diff & Comparison table in Patcher drawer
        renderDiffBox(data.diff);

        const area = document.getElementById('patcherContentArea');
        const compTitle = document.createElement('h4');
        compTitle.style.fontSize = '0.95rem';
        compTitle.style.fontWeight = '700';
        compTitle.style.margin = '20px 0 8px';
        compTitle.style.color = '#1C1917';
        compTitle.textContent = 'After-Fix Verification Results';
        area.appendChild(compTitle);

        const table = document.createElement('table');
        table.className = 'compare-table';
        const thead = document.createElement('thead');
        thead.innerHTML = '<tr><th>Test Function</th><th>Before</th><th>After</th><th>Outcome</th></tr>';
        table.appendChild(thead);

        const tbody = document.createElement('tbody');
        const beforeMap = {};
        (data.before || []).forEach(b => { beforeMap[b.name] = b; });

        (data.after || []).forEach(aft => {
          const bef = beforeMap[aft.name] || {};
          const tr = document.createElement('tr');

          const tdName = document.createElement('td');
          tdName.className = 'mono';
          tdName.style.fontWeight = '600';
          tdName.textContent = aft.name;

          const tdBef = document.createElement('td');
          tdBef.appendChild(getVerdictPill(bef.verdict));

          const tdAft = document.createElement('td');
          tdAft.appendChild(getVerdictPill(aft.verdict));

          const tdOut = document.createElement('td');
          const isHealed = bef.verdict !== aft.verdict && aft.verdict === 'STABLE';
          if (isHealed) {
            const hPill = document.createElement('span');
            hPill.className = 'verdict-pill pill-stable';
            hPill.textContent = 'HEALED';
            tdOut.appendChild(hPill);
          } else if (aft.verdict === 'BROKEN_BUILD') {
            const bPill = document.createElement('span');
            bPill.className = 'verdict-pill pill-broken';
            bPill.textContent = 'GENUINE BUG';
            tdOut.appendChild(bPill);
          } else {
            const uPill = document.createElement('span');
            uPill.className = 'verdict-pill pill-stable';
            uPill.textContent = 'UNCHANGED';
            tdOut.appendChild(uPill);
          }

          tr.appendChild(tdName);
          tr.appendChild(tdBef);
          tr.appendChild(tdAft);
          tr.appendChild(tdOut);
          tbody.appendChild(tr);
        });
        table.appendChild(tbody);
        area.appendChild(table);

        document.getElementById('section-patcher').scrollIntoView({ behavior: 'smooth' });

        // Reload content into editor
        const updatedRes = await fetch('/api/files');
        const updatedData = await updatedRes.json();
        const updatedFile = (updatedData.files || []).find(f => f.path === targetPath);
        if (updatedFile) {
          customCodeArea.value = updatedFile.content;
        }
      } catch (err) {
        stopTimer();
        const statusText = document.getElementById('card3StatusText');
        statusText.style.color = '#991B1B';
        statusText.textContent = `Error: ${err.message}`;
      } finally {
        setButtonsDisabled(false);
      }
    }

    // Restore Original
    async function restoreOriginal() {
      const targetPath = lastScanData ? lastScanData.file_path : suiteSelect.value;
      if (!targetPath) return;

      setButtonsDisabled(true);
      try {
        const res = await fetch('/api/fix', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ file_path: targetPath, action: 'restore' })
        });
        const data = await res.json();
        
        const statusText = document.getElementById('card3StatusText');
        statusText.style.color = '#14532D';
        statusText.textContent = 'Original Restored';

        const area = document.getElementById('patcherContentArea');
        area.innerHTML = '';
        const ph = document.createElement('div');
        ph.className = 'drawer-placeholder';
        ph.textContent = 'Run a scan, then click Preview AST Patch';
        area.appendChild(ph);

        await loadFiles();
      } catch (err) {
        alert('Failed to restore backup: ' + err.message);
      } finally {
        setButtonsDisabled(false);
      }
    }

    document.getElementById('btnScan').addEventListener('click', runScan);
    document.getElementById('btnApplyFix').addEventListener('click', applyFix);
    document.getElementById('btnRestore').addEventListener('click', restoreOriginal);

    window.addEventListener('DOMContentLoaded', loadFiles);
  </script>
</body>
</html>
"""


def _is_safe_test_path(path_str: str) -> bool:
    """Validate that path contains no traversal and is within allowed directories."""
    if not path_str or ".." in path_str:
        return False
    try:
        p = Path(path_str)
        cwd = Path.cwd().resolve()
        temp_dir = Path(tempfile.gettempdir()).resolve()
        allowed_dirs = [
            (cwd / "demo_sick_repo").resolve(),
            (cwd / "benchmark_suites").resolve(),
            temp_dir,
        ]
        resolved = p.resolve() if p.is_absolute() else (cwd / p).resolve()
        for ad in allowed_dirs:
            if resolved == ad:
                return True
            try:
                if resolved.is_relative_to(ad):
                    return True
            except AttributeError:
                if ad in resolved.parents:
                    return True
        return False
    except Exception:
        return False


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


CACHE_DIR = Path(".flakecache")
JOBS: Dict[str, Dict[str, Any]] = {}
SCAN_LOCK = threading.Lock()
IS_SCAN_RUNNING = False


def _get_cache_key(content: str) -> str:
    key_src = (content + ENGINE_VERSION).encode("utf-8")
    return hashlib.sha256(key_src).hexdigest()


def _read_cache(cache_key: str) -> Optional[Dict[str, Any]]:
    cache_file = CACHE_DIR / f"{cache_key}.json"
    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def _write_cache(cache_key: str, data: Dict[str, Any]) -> None:
    CACHE_DIR.mkdir(exist_ok=True)
    cache_file = CACHE_DIR / f"{cache_key}.json"
    try:
        cache_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass


def _run_scan_job(job_id: str, target_file: Path, content: str, cache_key: str) -> None:
    global IS_SCAN_RUNNING
    t0 = time.monotonic()
    try:
        def on_progress(phase: str, step: int, total: int) -> None:
            with SCAN_LOCK:
                if job_id in JOBS:
                    JOBS[job_id]["progress"] = {
                        "phase": phase,
                        "step": step,
                        "total": total,
                        "elapsed": round(time.monotonic() - t0, 1),
                    }

        reports = diagnose(target_file, progress_callback=on_progress)
        _, diff = build_patch(target_file, reports)
        elapsed = time.monotonic() - t0
        sub_count = getattr(reports[0], "_subprocess_count", 0) if reports else 0
        timings = getattr(reports[0], "_timings", {}) if reports else {}

        result = {
            "results": [r.to_dict() for r in reports],
            "diff": diff,
            "file_path": target_file.as_posix(),
            "scan_time": round(elapsed, 2),
            "subprocess_count": sub_count,
            "timings": timings,
        }
        _write_cache(cache_key, result)

        with SCAN_LOCK:
            JOBS[job_id]["status"] = "done"
            JOBS[job_id]["result"] = result
    except Exception as e:
        with SCAN_LOCK:
            JOBS[job_id]["status"] = "error"
            JOBS[job_id]["error"] = str(e)
    finally:
        with SCAN_LOCK:
            IS_SCAN_RUNNING = False


def _prewarm_cache() -> None:
    demo_path = Path("demo_sick_repo/test_patient_zero.py")
    if demo_path.exists():
        try:
            content = demo_path.read_text(encoding="utf-8")
            ck = _get_cache_key(content)
            if _read_cache(ck) is None:
                reports = diagnose(demo_path)
                _, diff = build_patch(demo_path, reports)
                sub_count = getattr(reports[0], "_subprocess_count", 0) if reports else 0
                timings = getattr(reports[0], "_timings", {}) if reports else {}
                elapsed = getattr(reports[0], "_scan_elapsed", 0.0) if reports else 0.0
                result = {
                    "results": [r.to_dict() for r in reports],
                    "diff": diff,
                    "file_path": demo_path.as_posix(),
                    "scan_time": round(elapsed, 2),
                    "subprocess_count": sub_count,
                    "timings": timings,
                }
                _write_cache(ck, result)
        except Exception:
            pass


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
            allow_custom = "true" if os.environ.get("FD_ALLOW_CUSTOM_CODE", "0") == "1" else "false"
            html_content = (
                HTML_PAGE_TEMPLATE
                .replace("__PAGE_TITLE__", "Flake Doctor | Forensic Test Diagnostics")
                .replace("__ALLOW_CUSTOM_CODE__", allow_custom)
            )
            self._send_html(html_content)
        elif parsed.path == "/api/files":
            files = _get_all_test_files()
            self._send_json({"files": files})
        elif parsed.path.startswith("/api/scan/"):
            job_id = parsed.path[len("/api/scan/"):].strip()
            with SCAN_LOCK:
                job = JOBS.get(job_id)
            if not job:
                self._send_json({"error": "Job not found"}, 404)
            elif job["status"] == "done":
                res_data = dict(job["result"])
                res_data["job_id"] = job_id
                res_data["status"] = "done"
                self._send_json(res_data, 200)
            elif job["status"] == "error":
                self._send_json({"job_id": job_id, "status": "error", "error": job.get("error", "Unknown error")}, 500)
            else:
                self._send_json({"job_id": job_id, "status": "running", "progress": job.get("progress")}, 200)
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length > 20 * 1024:
            self._send_json({"error": "payload too large (max 20KB)"}, 413)
            return

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
        bypass_cache = bool(req_data.get("bypass_cache", False))

        if custom_code is not None:
            # Check if custom code execution is allowed
            if os.environ.get("FD_ALLOW_CUSTOM_CODE", "0") != "1":
                self._send_json({"error": "custom code disabled on this deployment"}, 403)
                return

            # Validate client IP (localhost only)
            client_ip = self.client_address[0]
            if client_ip not in ("127.0.0.1", "localhost", "::1"):
                self._send_json({"error": "custom code only permitted from localhost"}, 403)
                return

            # Execute in tempdir with minimal env
            os.environ["FD_MINIMAL_ENV"] = "1"
            tmp_custom_dir = Path(tempfile.mkdtemp(prefix="fd_custom_"))
            target_file = tmp_custom_dir / "custom_test.py"
            target_file.write_text(custom_code, encoding="utf-8")
            content = custom_code
        elif file_path_str:
            if not _is_safe_test_path(file_path_str):
                self._send_json({"error": "Path traversal or forbidden path"}, 400)
                return
            target_file = Path(file_path_str)
            if not target_file.exists():
                self._send_json({"error": f"File not found: {target_file}"}, 404)
                return
            content = target_file.read_text(encoding="utf-8")
        else:
            self._send_json({"error": "Missing file_path or custom_code"}, 400)
            return

        cache_key = _get_cache_key(content)
        job_id = str(uuid.uuid4())

        # Check cache if not bypassed
        if not bypass_cache:
            cached_result = _read_cache(cache_key)
            if cached_result is not None:
                res_data = dict(cached_result)
                res_data["cached"] = True
                res_data["job_id"] = job_id
                res_data["status"] = "done"
                with SCAN_LOCK:
                    JOBS[job_id] = {"status": "done", "result": res_data, "progress": None}
                self._send_json(res_data, 200)
                return

        # Concurrency check
        global IS_SCAN_RUNNING
        with SCAN_LOCK:
            if IS_SCAN_RUNNING:
                self._send_json({"error": "scan in progress, try again later"}, 409)
                return
            IS_SCAN_RUNNING = True
            JOBS[job_id] = {
                "status": "running",
                "progress": {"phase": "starting", "step": 0, "total": 5, "elapsed": 0.0},
            }

        worker = threading.Thread(
            target=_run_scan_job,
            args=(job_id, target_file, content, cache_key),
            daemon=True,
        )
        worker.start()

        self._send_json({"job_id": job_id, "status": "running"}, 202)

    def _handle_fix(self, req_data: Dict[str, Any]) -> None:
        file_path_str = req_data.get("file_path")
        action = req_data.get("action", "apply")

        if not file_path_str:
            self._send_json({"error": "Missing file_path"}, 400)
            return

        if not _is_safe_test_path(file_path_str):
            self._send_json({"error": "Path traversal or forbidden path"}, 400)
            return

        target_file = Path(file_path_str)
        bak_file = target_file.with_name(target_file.name + ".bak")

        if action == "restore":
            if bak_file.exists():
                try:
                    shutil.copy2(bak_file, target_file)
                    bak_file.unlink(missing_ok=True)
                except OSError:
                    pass
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

                # 4. Fix verification on patched source
                vres = verify_fix(target_file, patched_src, before_reports=before_reports)
                after_reports = vres.reports

                # Write patched source to target file
                target_file.write_text(patched_src, encoding="utf-8")

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
                    "diff": vres.diff or diff,
                    "healed": healed,
                    "remaining_bugs": remaining_bugs,
                    "verified_file": vres.verified_file,
                    "patched_sha256": vres.patched_sha256,
                    "outcomes": vres.outcomes,
                })
            except Exception as e:
                self._send_json({"error": str(e)}, 500)


def run_server(port: int = 8080) -> None:
    """Launch the Flake Doctor Web Server bound to 127.0.0.1."""
    server_address = ("127.0.0.1", port)
    httpd = ThreadingHTTPServer(server_address, FlakeDoctorHandler)
    print(f"Flake Doctor Web Console running at http://127.0.0.1:{port}")
    # Pre-warm cache for demo test file in background
    threading.Thread(target=_prewarm_cache, daemon=True).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down Flake Doctor Web Console.")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    run_server(port)
