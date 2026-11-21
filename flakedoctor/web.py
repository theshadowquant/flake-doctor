"""Flake Doctor Live Local Web Dashboard.

Zero external dependencies - built entirely on Python standard library http.server.
Bespoke editorial studio design system with warm peach-sand-sage palette.
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
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=JetBrains+Mono:wght@400;500;600&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    :root {
      --canvas: #F5EBE3;
      --surface-white: #FCFBF9;
      --surface-sand: #F6EDE1;
      --surface-sage: #E7EFEA;
      --surface-slate: #1E293B;
      --surface-slate-subtle: #2D3A4F;
      --text-ink: #1C1917;
      --text-muted: #57534E;
      --text-kicker: #78716C;
      --text-light: #F8FAFC;
      --text-light-muted: #94A3B8;
      --border-subtle: rgba(28, 25, 23, 0.08);
      --border-card: rgba(28, 25, 23, 0.06);
      --border-white: rgba(255, 255, 255, 0.7);
      --shadow-sm: 0 4px 12px rgba(28, 25, 23, 0.03);
      --shadow-md: 0 10px 30px rgba(28, 25, 23, 0.035);
      --shadow-lg: 0 20px 40px rgba(28, 25, 23, 0.06);
      --radius-sm: 10px;
      --radius-md: 16px;
      --radius-lg: 24px;
      --radius-pill: 9999px;
      --font-serif: 'Instrument Serif', Georgia, serif;
      --font-sans: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif;
      --font-mono: 'JetBrains Mono', monospace;

      /* Archetype tints */
      --badge-polluter-bg: #FEF3C7;
      --badge-polluter-text: #92400E;
      --badge-polluter-border: #FDE68A;

      --badge-order-bg: #F3E8FF;
      --badge-order-text: #6B21A8;
      --badge-order-border: #E9D5FF;

      --badge-prng-bg: #FEF9C3;
      --badge-prng-text: #854D0E;
      --badge-prng-border: #FEF08A;

      --badge-timing-bg: #E0F2FE;
      --badge-timing-text: #0369A1;
      --badge-timing-border: #BAE6FD;

      --badge-broken-bg: #FEE2E2;
      --badge-broken-text: #991B1B;
      --badge-broken-border: #FECACA;

      --badge-stable-bg: #DCFCE7;
      --badge-stable-text: #166534;
      --badge-stable-border: #BBF7D0;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      background: linear-gradient(155deg, #F6DFD3 0%, #F5EBE3 42%, #EAECE7 78%, #E2E9E5 100%);
      color: var(--text-ink);
      font-family: var(--font-sans);
      min-height: 100vh;
      line-height: 1.5;
      padding-bottom: 96px;
      -webkit-font-smoothing: antialiased;
    }

    code, pre, .mono {
      font-family: var(--font-mono);
    }

    /* Floating Pill Navbar */
    .nav-wrapper {
      position: sticky;
      top: 18px;
      z-index: 100;
      padding: 0 24px;
      display: flex;
      justify-content: center;
      margin-bottom: 32px;
    }
    .pill-navbar {
      width: 100%;
      max-width: 1200px;
      background: rgba(252, 250, 247, 0.88);
      backdrop-filter: blur(14px);
      -webkit-backdrop-filter: blur(14px);
      border-radius: var(--radius-pill);
      border: 1px solid var(--border-white);
      box-shadow: 0 8px 30px rgba(28, 25, 23, 0.04);
      padding: 10px 24px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
    }
    .nav-brand {
      display: flex;
      align-items: center;
      gap: 12px;
      text-decoration: none;
      color: var(--text-ink);
    }
    .nav-brand-pulse {
      width: 10px;
      height: 10px;
      border-radius: 50%;
      background: #10B981;
      box-shadow: 0 0 10px rgba(16, 185, 129, 0.6);
      animation: navPulse 2s infinite ease-in-out;
    }
    @keyframes navPulse {
      0%, 100% { opacity: 0.5; transform: scale(0.9); }
      50% { opacity: 1; transform: scale(1.15); }
    }
    .nav-brand-title {
      font-family: var(--font-sans);
      font-weight: 800;
      font-size: 0.95rem;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      color: var(--text-ink);
    }
    .nav-brand-version {
      font-size: 0.7rem;
      font-weight: 600;
      background: var(--surface-sand);
      color: var(--text-kicker);
      padding: 2px 8px;
      border-radius: var(--radius-pill);
      border: 1px solid var(--border-card);
      letter-spacing: 0.04em;
    }
    .nav-links {
      display: flex;
      align-items: center;
      gap: 24px;
      list-style: none;
    }
    .nav-links a {
      text-decoration: none;
      color: var(--text-muted);
      font-size: 0.86rem;
      font-weight: 600;
      transition: color 0.15s ease;
    }
    .nav-links a:hover {
      color: var(--text-ink);
    }
    .nav-badge-pill {
      display: flex;
      align-items: center;
      gap: 8px;
      background: var(--surface-slate);
      color: var(--text-light);
      padding: 6px 14px;
      border-radius: var(--radius-pill);
      font-size: 0.72rem;
      font-weight: 600;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }
    .nav-badge-dot {
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: #38BDF8;
    }

    /* Container */
    .container {
      max-width: 1240px;
      margin: 0 auto;
      padding: 0 24px;
    }

    /* Editorial Hero Section */
    .hero-grid {
      display: grid;
      grid-template-columns: 1.15fr 0.85fr;
      gap: 32px;
      align-items: stretch;
      margin-bottom: 36px;
    }
    .hero-narrative {
      padding: 20px 8px 12px 0;
      display: flex;
      flex-direction: column;
      justify-content: center;
    }
    .micro-kicker {
      font-size: 0.72rem;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      font-weight: 700;
      color: var(--text-kicker);
      margin-bottom: 14px;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .micro-kicker::before {
      content: '';
      display: inline-block;
      width: 14px;
      height: 2px;
      background: var(--text-kicker);
      border-radius: 1px;
    }
    .hero-headline {
      font-family: var(--font-serif);
      font-size: 3.5rem;
      font-weight: 400;
      line-height: 1.05;
      letter-spacing: -0.02em;
      color: var(--text-ink);
      margin-bottom: 18px;
    }
    .hero-headline em {
      font-style: italic;
      color: #92400E;
    }
    .hero-body {
      font-size: 1.02rem;
      color: var(--text-muted);
      line-height: 1.6;
      max-width: 580px;
      margin-bottom: 24px;
    }
    .meta-pills-row {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }
    .meta-pill {
      font-size: 0.74rem;
      font-weight: 600;
      padding: 6px 14px;
      border-radius: var(--radius-pill);
      background: rgba(255, 255, 255, 0.65);
      border: 1px solid var(--border-card);
      color: var(--text-muted);
      letter-spacing: 0.02em;
    }

    /* Bento Control Card */
    .bento-card {
      background: var(--surface-white);
      border-radius: var(--radius-lg);
      border: 1px solid var(--border-card);
      box-shadow: var(--shadow-md);
      padding: 28px;
      position: relative;
    }
    .card-header-label {
      font-size: 0.72rem;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      font-weight: 700;
      color: var(--text-kicker);
      margin-bottom: 12px;
    }
    .control-group {
      margin-bottom: 18px;
    }
    .control-label {
      display: block;
      font-size: 0.82rem;
      font-weight: 600;
      color: var(--text-ink);
      margin-bottom: 6px;
    }
    .select-input, .code-textarea {
      width: 100%;
      background: #FFFFFF;
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-sm);
      padding: 10px 14px;
      font-size: 0.86rem;
      color: var(--text-ink);
      font-family: var(--font-sans);
      outline: none;
      transition: border-color 0.15s ease, box-shadow 0.15s ease;
    }
    .select-input:focus, .code-textarea:focus {
      border-color: var(--surface-slate);
      box-shadow: 0 0 0 3px rgba(30, 41, 59, 0.08);
    }
    .code-textarea {
      font-family: var(--font-mono);
      font-size: 0.8rem;
      min-height: 120px;
      resize: vertical;
      line-height: 1.45;
    }
    .btn-row {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 20px;
    }
    .btn-pill {
      border-radius: var(--radius-pill);
      padding: 10px 20px;
      font-size: 0.82rem;
      font-weight: 600;
      letter-spacing: 0.02em;
      cursor: pointer;
      border: 1px solid transparent;
      display: inline-flex;
      align-items: center;
      gap: 8px;
      transition: all 0.15s ease;
      font-family: var(--font-sans);
    }
    .btn-primary {
      background: var(--surface-slate);
      color: var(--text-light);
      box-shadow: 0 4px 14px rgba(30, 41, 59, 0.16);
    }
    .btn-primary:hover {
      background: #0F172A;
      transform: translateY(-1px);
    }
    .btn-secondary {
      background: var(--surface-sand);
      color: var(--text-ink);
      border: 1px solid rgba(28, 25, 23, 0.1);
    }
    .btn-secondary:hover {
      background: #EFE4D6;
    }
    .btn-sage {
      background: var(--surface-sage);
      color: #14532D;
      border: 1px solid #BBF7D0;
    }
    .btn-sage:hover {
      background: #D8E7DE;
    }
    .btn-subtle {
      background: transparent;
      color: var(--text-muted);
      border: 1px solid var(--border-subtle);
    }
    .btn-subtle:hover {
      background: rgba(28, 25, 23, 0.04);
      color: var(--text-ink);
    }

    /* 3-Column Bento Metrics Grid */
    .metrics-bento-grid {
      display: grid;
      grid-template-columns: 1.35fr 1fr 1fr;
      gap: 20px;
      margin-bottom: 36px;
    }
    .bento-slate-card {
      background: var(--surface-slate);
      color: var(--text-light);
      border-radius: var(--radius-lg);
      padding: 26px 28px;
      box-shadow: var(--shadow-lg);
      position: relative;
      overflow: hidden;
      border: 1px solid rgba(255, 255, 255, 0.1);
    }
    .bento-slate-card::after {
      content: '';
      position: absolute;
      top: -30px;
      right: -30px;
      width: 140px;
      height: 140px;
      border-radius: 50%;
      background: radial-gradient(circle, rgba(56, 189, 248, 0.15) 0%, rgba(30, 41, 59, 0) 70%);
      pointer-events: none;
    }
    .slate-kicker {
      color: var(--text-light-muted);
      font-size: 0.72rem;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      font-weight: 700;
      margin-bottom: 12px;
    }
    .slate-hero-stat {
      font-family: var(--font-serif);
      font-size: 3.2rem;
      font-weight: 400;
      line-height: 1;
      margin-bottom: 8px;
      letter-spacing: -0.02em;
    }
    .slate-sub-stat {
      font-size: 0.86rem;
      color: var(--text-light-muted);
      margin-bottom: 18px;
    }
    .slate-pills-row {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 14px;
      padding-top: 14px;
      border-top: 1px solid rgba(255, 255, 255, 0.12);
    }
    .slate-mini-pill {
      font-size: 0.7rem;
      font-family: var(--font-mono);
      background: rgba(255, 255, 255, 0.08);
      color: #E2E8F0;
      padding: 4px 10px;
      border-radius: var(--radius-pill);
      border: 1px solid rgba(255, 255, 255, 0.08);
    }

    .bento-sand-card {
      background: var(--surface-sand);
      border-radius: var(--radius-lg);
      padding: 26px 28px;
      border: 1px solid rgba(28, 25, 23, 0.08);
      box-shadow: var(--shadow-sm);
      display: flex;
      flex-direction: column;
      justify-content: space-between;
    }
    .sand-stat-number {
      font-family: var(--font-serif);
      font-size: 3.2rem;
      line-height: 1;
      color: #92400E;
      margin-bottom: 6px;
    }
    .sand-archetypes-list {
      list-style: none;
      display: flex;
      flex-direction: column;
      gap: 6px;
      margin-top: 14px;
    }
    .sand-archetype-row {
      display: flex;
      justify-content: space-between;
      font-size: 0.78rem;
      font-weight: 600;
      color: var(--text-muted);
    }

    .bento-sage-card {
      background: var(--surface-sage);
      border-radius: var(--radius-lg);
      padding: 26px 28px;
      border: 1px solid rgba(28, 25, 23, 0.08);
      box-shadow: var(--shadow-sm);
      display: flex;
      flex-direction: column;
      justify-content: space-between;
    }
    .sage-stat-number {
      font-family: var(--font-serif);
      font-size: 3.2rem;
      line-height: 1;
      color: #14532D;
      margin-bottom: 6px;
    }

    /* Structured Forensic Autopsy List */
    .section-headline-row {
      display: flex;
      justify-content: space-between;
      align-items: flex-end;
      margin-bottom: 18px;
      padding: 0 4px;
    }
    .section-title {
      font-family: var(--font-serif);
      font-size: 2rem;
      font-weight: 400;
      color: var(--text-ink);
      line-height: 1.1;
    }
    .section-subtitle {
      font-size: 0.84rem;
      color: var(--text-muted);
      margin-top: 4px;
    }

    .autopsy-card {
      background: var(--surface-white);
      border-radius: var(--radius-lg);
      border: 1px solid var(--border-card);
      box-shadow: var(--shadow-md);
      overflow: hidden;
      margin-bottom: 36px;
    }
    .autopsy-header-row {
      display: grid;
      grid-template-columns: 2.2fr 1.1fr 2.3fr 2.6fr 1fr;
      padding: 14px 24px;
      background: #F8F6F2;
      border-bottom: 1px solid var(--border-subtle);
      font-size: 0.72rem;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      font-weight: 700;
      color: var(--text-kicker);
    }
    .autopsy-row {
      display: grid;
      grid-template-columns: 2.2fr 1.1fr 2.3fr 2.6fr 1fr;
      padding: 20px 24px;
      border-bottom: 1px solid rgba(28, 25, 23, 0.05);
      align-items: start;
      transition: background 0.15s ease;
    }
    .autopsy-row:last-child {
      border-bottom: none;
    }
    .autopsy-row:hover {
      background: #FAF8F5;
    }

    /* Column Styles */
    .col-test-name {
      display: flex;
      flex-direction: column;
      gap: 6px;
    }
    .test-func-title {
      font-family: var(--font-mono);
      font-size: 0.88rem;
      font-weight: 600;
      color: var(--text-ink);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .test-func-meta {
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .sweep-badge {
      font-size: 0.68rem;
      font-family: var(--font-mono);
      background: rgba(28, 25, 23, 0.05);
      color: var(--text-muted);
      padding: 2px 7px;
      border-radius: var(--radius-pill);
    }

    /* Verdict Badges */
    .verdict-badge {
      display: inline-flex;
      align-items: center;
      padding: 4px 10px;
      border-radius: var(--radius-pill);
      font-size: 0.72rem;
      font-weight: 700;
      letter-spacing: 0.03em;
      width: fit-content;
      border: 1px solid transparent;
    }
    .badge-polluter {
      background: var(--badge-polluter-bg);
      color: var(--badge-polluter-text);
      border-color: var(--badge-polluter-border);
    }
    .badge-order {
      background: var(--badge-order-bg);
      color: var(--badge-order-text);
      border-color: var(--badge-order-border);
    }
    .badge-prng {
      background: var(--badge-prng-bg);
      color: var(--badge-prng-text);
      border-color: var(--badge-prng-border);
    }
    .badge-timing {
      background: var(--badge-timing-bg);
      color: var(--badge-timing-text);
      border-color: var(--badge-timing-border);
    }
    .badge-broken {
      background: var(--badge-broken-bg);
      color: var(--badge-broken-text);
      border-color: var(--badge-broken-border);
    }
    .badge-stable {
      background: var(--badge-stable-bg);
      color: var(--badge-stable-text);
      border-color: var(--badge-stable-border);
    }

    .col-root-cause {
      font-size: 0.82rem;
      color: var(--text-muted);
      line-height: 1.45;
      padding-right: 14px;
    }
    .culprit-tag {
      display: inline-block;
      margin-top: 4px;
      font-family: var(--font-mono);
      font-size: 0.72rem;
      background: #FDE68A;
      color: #78350F;
      padding: 2px 6px;
      border-radius: 4px;
    }

    .ast-prescription-box {
      background: var(--surface-sand);
      border: 1px solid rgba(28, 25, 23, 0.08);
      border-radius: var(--radius-sm);
      padding: 10px 12px;
      font-size: 0.78rem;
    }
    .ast-line-pill {
      display: inline-block;
      font-family: var(--font-mono);
      font-size: 0.7rem;
      font-weight: 600;
      color: var(--text-kicker);
      margin-bottom: 4px;
    }
    .ast-prescription-text {
      color: var(--text-ink);
      line-height: 1.35;
      font-size: 0.78rem;
    }

    .col-clean-runs {
      font-family: var(--font-mono);
      font-size: 0.84rem;
      font-weight: 600;
      color: var(--text-ink);
      display: flex;
      flex-direction: column;
      gap: 2px;
    }
    .clean-runs-sub {
      font-size: 0.68rem;
      font-weight: 400;
      color: var(--text-kicker);
    }

    /* AST Unified Diff Section */
    .diff-section-card {
      background: var(--surface-white);
      border-radius: var(--radius-lg);
      border: 1px solid var(--border-card);
      box-shadow: var(--shadow-md);
      padding: 28px;
      margin-bottom: 36px;
    }
    .diff-pre {
      background: #181E29;
      color: #E2E8F0;
      border-radius: var(--radius-md);
      padding: 18px 20px;
      font-family: var(--font-mono);
      font-size: 0.8rem;
      line-height: 1.5;
      overflow-x: auto;
      max-height: 380px;
    }
    .diff-line-add {
      background: rgba(16, 185, 129, 0.2);
      color: #6EE7B7;
      display: block;
      margin: 0 -20px;
      padding: 0 20px;
    }
    .diff-line-del {
      background: rgba(239, 68, 68, 0.2);
      color: #FCA5A5;
      display: block;
      margin: 0 -20px;
      padding: 0 20px;
    }
    .diff-line-hdr {
      color: #38BDF8;
      font-weight: 600;
    }

    /* Before / After Table */
    .compare-table {
      width: 100%;
      border-collapse: collapse;
      margin-top: 16px;
      font-size: 0.84rem;
    }
    .compare-table th {
      text-align: left;
      font-size: 0.72rem;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--text-kicker);
      padding: 10px 14px;
      border-bottom: 1px solid var(--border-subtle);
    }
    .compare-table td {
      padding: 12px 14px;
      border-bottom: 1px solid rgba(28, 25, 23, 0.05);
    }

    /* 4-Step Walkthrough Section */
    .walkthrough-grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 18px;
      margin-bottom: 36px;
    }
    .step-card {
      background: var(--surface-white);
      border-radius: var(--radius-md);
      border: 1px solid var(--border-card);
      padding: 22px 20px;
      box-shadow: var(--shadow-sm);
      display: flex;
      flex-direction: column;
      justify-content: space-between;
    }
    .step-number {
      font-family: var(--font-serif);
      font-size: 1.8rem;
      line-height: 1;
      color: #92400E;
      margin-bottom: 10px;
    }
    .step-title {
      font-size: 0.9rem;
      font-weight: 700;
      color: var(--text-ink);
      margin-bottom: 8px;
    }
    .step-desc {
      font-size: 0.78rem;
      color: var(--text-muted);
      line-height: 1.5;
    }
    .formula-box {
      margin-top: 10px;
      background: var(--surface-sand);
      padding: 6px 10px;
      border-radius: 6px;
      font-family: var(--font-mono);
      font-size: 0.72rem;
      color: var(--text-ink);
      text-align: center;
    }

    /* Empty & Loading States */
    .empty-state {
      padding: 60px 24px;
      text-align: center;
      color: var(--text-muted);
    }
    .spinner {
      display: inline-block;
      width: 16px;
      height: 16px;
      border: 2px solid rgba(255, 255, 255, 0.3);
      border-top-color: #FFFFFF;
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
    }
    @keyframes spin {
      to { transform: rotate(360deg); }
    }

    /* Responsive */
    @media (max-width: 1024px) {
      .hero-grid { grid-template-columns: 1fr; }
      .metrics-bento-grid { grid-template-columns: 1fr; }
      .walkthrough-grid { grid-template-columns: 1fr 1fr; }
      .autopsy-header-row, .autopsy-row {
        grid-template-columns: 1fr;
        gap: 12px;
      }
    }
  </style>
</head>
<body>

  <!-- Floating Pill Navbar -->
  <div class="nav-wrapper">
    <nav class="pill-navbar">
      <a href="#" class="nav-brand">
        <div class="nav-brand-pulse"></div>
        <span class="nav-brand-title">Flake Doctor</span>
        <span class="nav-brand-version">v1.0.0</span>
      </a>
      <ul class="nav-links">
        <li><a href="#diagnostics">Diagnostics</a></li>
        <li><a href="#autopatch">AST Auto-Patcher</a></li>
        <li><a href="#methodology">How It Works</a></li>
      </ul>
      <div class="nav-badge-pill">
        <div class="nav-badge-dot"></div>
        <span>TEAM DUST_BUSTERS | PS ID: OI</span>
      </div>
    </nav>
  </div>

  <main class="container">

    <!-- 2-Column Asymmetric Editorial Hero -->
    <section class="hero-grid" id="diagnostics">
      <div class="hero-narrative">
        <div class="micro-kicker">Forensic Flakiness Engine & AST Synthesizer</div>
        <h1 class="hero-headline">Diagnose, isolate, and <em>heal</em> flaky tests.</h1>
        <p class="hero-body">
          Flake Doctor eliminates CI non-determinism with dynamic isolation matrices, unseeded PRNG sweepers, thread-scheduler contention injection, and surgical AST code rewrite synthesizers.
        </p>
        <div class="meta-pills-row">
          <span class="meta-pill">Surgical AST Healing</span>
          <span class="meta-pill">Bisect State Isolation</span>
          <span class="meta-pill">Zero External Web Frameworks</span>
          <span class="meta-pill">Confidence Runs Formula</span>
        </div>
      </div>

      <!-- Bento Control Card -->
      <div class="bento-card">
        <div class="card-header-label">Investigation Controls</div>

        <div class="control-group">
          <label class="control-label" for="suiteSelect">Target Benchmark Suite</label>
          <select id="suiteSelect" class="select-input">
            <option value="">Loading test suites...</option>
          </select>
        </div>

        <div class="control-group">
          <label class="control-label" for="customCodeArea">Or Paste Pytest Code</label>
          <textarea id="customCodeArea" class="code-textarea" placeholder="# Paste custom test functions here...&#10;def test_demo():&#10;    assert True"></textarea>
        </div>

        <div class="btn-row">
          <button id="btnScan" class="btn-pill btn-primary">
            <span id="scanBtnText">Run Forensic Scan</span>
          </button>
          <button id="btnPreviewPatch" class="btn-pill btn-secondary">
            <span>Preview AST Patch</span>
          </button>
          <button id="btnApplyFix" class="btn-pill btn-sage">
            <span>Apply Fix & Verify</span>
          </button>
          <button id="btnRestore" class="btn-pill btn-subtle">
            <span>Restore Original</span>
          </button>
        </div>
      </div>
    </section>

    <!-- 3-Column Bento Metrics Grid -->
    <section class="metrics-bento-grid">
      <!-- Card 1: Slate Metric -->
      <div class="bento-slate-card">
        <div class="slate-kicker">Suite Health & Confidence</div>
        <div class="slate-hero-stat" id="statHealth">--%</div>
        <div class="slate-sub-stat" id="statSubtitle">Awaiting diagnostic scan...</div>
        <div class="slate-pills-row">
          <span class="slate-mini-pill" id="pillTestsCount">0 Tests Checked</span>
          <span class="slate-mini-pill" id="pillDuration">0.00s Duration</span>
          <span class="slate-mini-pill" id="pillSubprocesses">0 Subprocesses</span>
        </div>
      </div>

      <!-- Card 2: Sand Metric -->
      <div class="bento-sand-card">
        <div>
          <div class="card-header-label" style="color: #92400E;">Flakiness Archetypes</div>
          <div class="sand-stat-number" id="statFlakesCount">0</div>
          <p style="font-size: 0.8rem; color: var(--text-muted);">Non-deterministic faults isolated</p>
        </div>
        <div class="sand-archetypes-list" id="archetypesBreakdown">
          <div class="sand-archetype-row"><span>State Pollution:</span><span id="countPolluter">0</span></div>
          <div class="sand-archetype-row"><span>Order Dependent:</span><span id="countOrder">0</span></div>
          <div class="sand-archetype-row"><span>Unseeded PRNG:</span><span id="countPrng">0</span></div>
          <div class="sand-archetype-row"><span>Timing Race:</span><span id="countTiming">0</span></div>
          <div class="sand-archetype-row"><span>Broken Build:</span><span id="countBroken">0</span></div>
        </div>
      </div>

      <!-- Card 3: Sage Metric -->
      <div class="bento-sage-card">
        <div>
          <div class="card-header-label" style="color: #14532D;">Synthesis & Auto-Heal</div>
          <div class="sage-stat-number" id="statHealedCount">0</div>
          <p style="font-size: 0.8rem; color: var(--text-muted);">Tests restored to STABLE state</p>
        </div>
        <div style="margin-top: 14px; font-size: 0.8rem; color: var(--text-muted); line-height: 1.45;" id="healStatusText">
          Auto-patching generates pytest fixtures and monkeypatch replacements without masking genuine bugs.
        </div>
      </div>
    </section>

    <!-- Structured Forensic Autopsy List -->
    <section>
      <div class="section-headline-row">
        <div>
          <h2 class="section-title">Forensic Autopsy Results</h2>
          <p class="section-subtitle">Individual test breakdowns with AST attribution and statistical failure bounds.</p>
        </div>
      </div>

      <div class="autopsy-card">
        <div class="autopsy-header-row">
          <div>Test Function</div>
          <div>Verdict</div>
          <div>Root Cause & Culprit</div>
          <div>AST Code Prescription</div>
          <div>Est. Clean Runs</div>
        </div>
        <div id="autopsyBody">
          <div class="empty-state">
            Select a target test suite above and click <strong>Run Forensic Scan</strong> to initiate autopsy.
          </div>
        </div>
      </div>
    </section>

    <!-- AST Unified Diff Section -->
    <section id="autopatch" class="diff-section-card" style="display: none;">
      <div class="section-headline-row">
        <div>
          <h2 class="section-title">Synthesized AST Patch</h2>
          <p class="section-subtitle">Automated source rewrite eliminating state pollution and order sensitivity.</p>
        </div>
      </div>
      <pre class="diff-pre" id="diffContent">No patch generated.</pre>

      <div id="compareWrapper" style="display: none; margin-top: 24px;">
        <h3 style="font-size: 1.1rem; font-weight: 700; margin-bottom: 8px;">Verification Comparison</h3>
        <table class="compare-table">
          <thead>
            <tr>
              <th>Test Function</th>
              <th>Before Verdict</th>
              <th>After Verdict</th>
              <th>Outcome</th>
            </tr>
          </thead>
          <tbody id="compareTableBody"></tbody>
        </table>
      </div>
    </section>

    <!-- 4-Step Walkthrough Section -->
    <section id="methodology" style="margin-top: 48px;">
      <div class="section-headline-row">
        <div>
          <h2 class="section-title">How Flake Doctor Works</h2>
          <p class="section-subtitle">Dynamic multi-stage isolation and statistical verification engine.</p>
        </div>
      </div>

      <div class="walkthrough-grid">
        <div class="step-card">
          <div>
            <div class="step-number">01</div>
            <div class="step-title">Order Shuffling & Bisect</div>
            <p class="step-desc">Runs standard order, reverse order, and targeted sub-matrix permutations to uncover state polluters and order-dependent consumers.</p>
          </div>
        </div>
        <div class="step-card">
          <div>
            <div class="step-number">02</div>
            <div class="step-title">PRNG Sweep Matrix</div>
            <p class="step-desc">Injects known seed variations into unseeded random calls to expose threshold flakiness and statistical variance errors.</p>
          </div>
        </div>
        <div class="step-card">
          <div>
            <div class="step-number">03</div>
            <div class="step-title">CPU Jitter & Timing Race</div>
            <p class="step-desc">Launches worker contention threads to provoke latent thread scheduling and event wait races.</p>
          </div>
        </div>
        <div class="step-card">
          <div>
            <div class="step-number">04</div>
            <div class="step-title">AST Synthesis & Bounds</div>
            <p class="step-desc">Synthesizes pytest fixtures and monkeypatches, bounding required verification runs by:</p>
          </div>
          <div class="formula-box">N = &lceil;ln(0.01) / ln(1 - p)&rceil;</div>
        </div>
      </div>
    </section>

  </main>

  <script>
    let currentFiles = [];
    let lastScanData = null;

    // Load available files on startup
    async function loadFiles() {
      try {
        const res = await fetch('/api/files');
        const data = await res.json();
        currentFiles = data.files || [];
        const select = document.getElementById('suiteSelect');
        select.innerHTML = '';
        currentFiles.forEach((f, idx) => {
          const opt = document.createElement('option');
          opt.value = f.path;
          opt.textContent = `${f.name} (${f.path.split('/')[0]})`;
          if (idx === 0) opt.selected = true;
          select.appendChild(opt);
        });
        if (currentFiles.length > 0) {
          document.getElementById('customCodeArea').value = currentFiles[0].content;
        }
      } catch (err) {
        console.error('Failed to load test files:', err);
      }
    }

    document.getElementById('suiteSelect').addEventListener('change', (e) => {
      const selected = currentFiles.find(f => f.path === e.target.value);
      if (selected) {
        document.getElementById('customCodeArea').value = selected.content;
      }
    });

    // Helper to get verdict badge class
    function getVerdictBadgeClass(verdict) {
      switch (verdict) {
        case 'STATE_POLLUTION': return 'badge-polluter';
        case 'ORDER_DEPENDENT': return 'badge-order';
        case 'UNSEEDED_PRNG': return 'badge-prng';
        case 'TIMING_RACE': return 'badge-timing';
        case 'BROKEN_BUILD': return 'badge-broken';
        case 'STABLE': return 'badge-stable';
        default: return 'badge-stable';
      }
    }

    // Run Forensic Scan
    async function runScan() {
      const btn = document.getElementById('btnScan');
      const textSpan = document.getElementById('scanBtnText');
      const suiteSelect = document.getElementById('suiteSelect');
      const customCode = document.getElementById('customCodeArea').value;

      btn.disabled = true;
      textSpan.innerHTML = '<span class="spinner"></span> Scanning...';

      try {
        const payload = {};
        const selectedFile = suiteSelect.value;
        const matching = currentFiles.find(f => f.path === selectedFile);
        
        // If code has been edited from the original file, send custom_code
        if (matching && matching.content.trim() === customCode.trim()) {
          payload.file_path = selectedFile;
        } else {
          payload.custom_code = customCode;
        }

        const res = await fetch('/api/scan', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });

        const data = await res.json();
        if (data.error) {
          alert('Scan error: ' + data.error);
          return;
        }

        lastScanData = data;
        renderResults(data);
      } catch (err) {
        alert('Network or server error during scan: ' + err.message);
      } finally {
        btn.disabled = false;
        textSpan.textContent = 'Run Forensic Scan';
      }
    }

    function renderResults(data) {
      const results = data.results || [];
      const autopsyBody = document.getElementById('autopsyBody');
      autopsyBody.innerHTML = '';

      if (results.length === 0) {
        autopsyBody.innerHTML = '<div class="empty-state">No tests found in target file.</div>';
        return;
      }

      let stableCount = 0;
      let polluterCount = 0;
      let orderCount = 0;
      let prngCount = 0;
      let timingCount = 0;
      let brokenCount = 0;

      results.forEach(r => {
        if (r.verdict === 'STABLE') stableCount++;
        else if (r.verdict === 'STATE_POLLUTION') polluterCount++;
        else if (r.verdict === 'ORDER_DEPENDENT') orderCount++;
        else if (r.verdict === 'UNSEEDED_PRNG') prngCount++;
        else if (r.verdict === 'TIMING_RACE') timingCount++;
        else if (r.verdict === 'BROKEN_BUILD') brokenCount++;

        const row = document.createElement('div');
        row.className = 'autopsy-row';

        // Col 1: Test function
        const failRatePct = (r.sweep_fail_rate * 100).toFixed(0);
        const col1 = `
          <div class="col-test-name">
            <span class="test-func-title" title="${r.name}">${r.name}</span>
            <div class="test-func-meta">
              <span class="sweep-badge">Fail Rate: ${failRatePct}%</span>
            </div>
          </div>
        `;

        // Col 2: Verdict
        const badgeClass = getVerdictBadgeClass(r.verdict);
        const col2 = `
          <div>
            <span class="verdict-badge ${badgeClass}">${r.verdict}</span>
          </div>
        `;

        // Col 3: Root cause
        let culpritHtml = '';
        if (r.culprit_predecessor) {
          culpritHtml = `<div class="culprit-tag">Culprit: ${r.culprit_predecessor}</div>`;
        }
        const col3 = `
          <div class="col-root-cause">
            <div>${r.root_cause || 'Deterministic behavior confirmed.'}</div>
            ${culpritHtml}
          </div>
        `;

        // Col 4: AST Prescription
        let astHtml = '<div style="color: var(--text-kicker); font-size: 0.78rem;">N/A</div>';
        if (r.ast_line !== null || r.code_prescription) {
          const lineStr = r.ast_line !== null ? `Line ${r.ast_line}` : 'AST';
          astHtml = `
            <div class="ast-prescription-box">
              <span class="ast-line-pill">${lineStr}</span>
              <div class="ast-prescription-text">${r.code_prescription || 'Review AST findings'}</div>
            </div>
          `;
        }
        const col4 = `<div>${astHtml}</div>`;

        // Col 5: Clean runs
        const cleanRuns = r.est_clean_runs_99 !== null ? r.est_clean_runs_99 : 'N/A';
        const col5 = `
          <div class="col-clean-runs">
            <span>${cleanRuns}</span>
            <span class="clean-runs-sub">${r.est_clean_runs_99 !== null ? 'runs (99%)' : 'deterministic'}</span>
          </div>
        `;

        row.innerHTML = col1 + col2 + col3 + col4 + col5;
        autopsyBody.appendChild(row);
      });

      // Update Summary Bento Cards
      const totalTests = results.length;
      const flakesCount = totalTests - stableCount;
      const healthPct = Math.round((stableCount / totalTests) * 100);

      document.getElementById('statHealth').textContent = `${healthPct}%`;
      document.getElementById('statSubtitle').textContent = `${stableCount} of ${totalTests} tests stable under stress`;
      document.getElementById('pillTestsCount').textContent = `${totalTests} Tests Evaluated`;
      document.getElementById('pillDuration').textContent = `${(data.scan_time || 0).toFixed(2)}s Scan Time`;
      document.getElementById('pillSubprocesses').textContent = `${data.subprocess_count || 0} Subprocesses`;

      document.getElementById('statFlakesCount').textContent = flakesCount;
      document.getElementById('countPolluter').textContent = polluterCount;
      document.getElementById('countOrder').textContent = orderCount;
      document.getElementById('countPrng').textContent = prngCount;
      document.getElementById('countTiming').textContent = timingCount;
      document.getElementById('countBroken').textContent = brokenCount;

      // Diff preview
      if (data.diff) {
        renderDiff(data.diff);
      }
    }

    function renderDiff(rawDiff) {
      const diffSection = document.getElementById('autopatch');
      const diffPre = document.getElementById('diffContent');
      if (!rawDiff || rawDiff.trim() === '') {
        diffSection.style.display = 'none';
        return;
      }
      diffSection.style.display = 'block';

      const lines = rawDiff.split('\n');
      const formatted = lines.map(line => {
        const escaped = line.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        if (line.startsWith('+') && !line.startsWith('+++')) {
          return `<span class="diff-line-add">${escaped}</span>`;
        } else if (line.startsWith('-') && !line.startsWith('---')) {
          return `<span class="diff-line-del">${escaped}</span>`;
        } else if (line.startsWith('@@') || line.startsWith('---') || line.startsWith('+++')) {
          return `<span class="diff-line-hdr">${escaped}</span>`;
        }
        return escaped;
      }).join('\n');

      diffPre.innerHTML = formatted;
    }

    // Preview Patch button
    document.getElementById('btnPreviewPatch').addEventListener('click', () => {
      if (lastScanData && lastScanData.diff) {
        renderDiff(lastScanData.diff);
        document.getElementById('autopatch').scrollIntoView({ behavior: 'smooth' });
      } else {
        alert('Please run a forensic scan first.');
      }
    });

    // Apply Fix & Verify
    async function applyFix() {
      const targetPath = lastScanData ? lastScanData.file_path : document.getElementById('suiteSelect').value;
      if (!targetPath) {
        alert('Please select or scan a target file first.');
        return;
      }

      const btn = document.getElementById('btnApplyFix');
      btn.disabled = true;
      btn.textContent = 'Applying & Verifying...';

      try {
        const res = await fetch('/api/fix', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ file_path: targetPath, action: 'apply' })
        });
        const data = await res.json();
        if (data.error) {
          alert('Fix error: ' + data.error);
          return;
        }

        document.getElementById('statHealedCount').textContent = data.healed || 0;
        document.getElementById('healStatusText').textContent = 
          `Auto-fix verified: ${data.healed} tests healed to STABLE. ${data.remaining_bugs || 0} genuine bug(s) remain.`;

        // Render Diff
        if (data.diff) renderDiff(data.diff);

        // Render Before/After Compare Table
        const compareWrapper = document.getElementById('compareWrapper');
        const compareTableBody = document.getElementById('compareTableBody');
        compareTableBody.innerHTML = '';

        const beforeMap = {};
        (data.before || []).forEach(b => beforeMap[b.name] = b);

        (data.after || []).forEach(aft => {
          const bef = beforeMap[aft.name] || {};
          const tr = document.createElement('tr');
          const isHealed = bef.verdict !== aft.verdict && aft.verdict === 'STABLE';
          const outcomeBadge = isHealed 
            ? '<span class="verdict-badge badge-stable">HEALED</span>'
            : (aft.verdict === 'BROKEN_BUILD' ? '<span class="verdict-badge badge-broken">GENUINE BUG</span>' : '<span class="verdict-badge badge-stable">UNCHANGED</span>');

          tr.innerHTML = `
            <td style="font-family: var(--font-mono); font-weight: 600;">${aft.name}</td>
            <td><span class="verdict-badge ${getVerdictBadgeClass(bef.verdict)}">${bef.verdict || 'N/A'}</span></td>
            <td><span class="verdict-badge ${getVerdictBadgeClass(aft.verdict)}">${aft.verdict}</span></td>
            <td>${outcomeBadge}</td>
          `;
          compareTableBody.appendChild(tr);
        });

        compareWrapper.style.display = 'block';
        document.getElementById('autopatch').style.display = 'block';
        document.getElementById('autopatch').scrollIntoView({ behavior: 'smooth' });

        // Reload the new content into the textarea
        const updatedRes = await fetch('/api/files');
        const updatedData = await updatedRes.json();
        const updatedFile = (updatedData.files || []).find(f => f.path === targetPath);
        if (updatedFile) {
          document.getElementById('customCodeArea').value = updatedFile.content;
        }
      } catch (err) {
        alert('Network or server error during fix: ' + err.message);
      } finally {
        btn.disabled = false;
        btn.textContent = 'Apply Fix & Verify';
      }
    }

    // Restore Original
    async function restoreOriginal() {
      const targetPath = lastScanData ? lastScanData.file_path : document.getElementById('suiteSelect').value;
      if (!targetPath) return;

      try {
        const res = await fetch('/api/fix', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ file_path: targetPath, action: 'restore' })
        });
        const data = await res.json();
        alert('Original test file restored from backup.');
        await loadFiles();
        document.getElementById('compareWrapper').style.display = 'none';
        document.getElementById('statHealedCount').textContent = '0';
        document.getElementById('healStatusText').textContent = 'Restored original test source code.';
      } catch (err) {
        alert('Failed to restore backup: ' + err.message);
      }
    }

    document.getElementById('btnScan').addEventListener('click', runScan);
    document.getElementById('btnApplyFix').addEventListener('click', applyFix);
    document.getElementById('btnRestore').addEventListener('click', restoreOriginal);

    // Initial load
    window.addEventListener('DOMContentLoaded', loadFiles);
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
