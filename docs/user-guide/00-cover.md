<!--
(cover-page
  :title "Arch Ascent User Guide"
  :version "1.0"
  :subtitle "Architectural Governance for Software Dependencies"
  :logo "screenshots/logo.png")
-->

<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">

<style>
/* Document-wide typography */
body, .markdown-body {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  font-size: 16px;
  line-height: 1.6;
  color: #24292f;
}

h1, h2, h3, h4, h5, h6 {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  font-weight: 600;
  line-height: 1.25;
  margin-top: 1.5em;
  margin-bottom: 0.5em;
}

code, pre, .monospace {
  font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  font-size: 0.9em;
}

pre {
  background: #f6f8fa;
  border-radius: 6px;
  padding: 1em;
  overflow-x: auto;
}

code {
  background: #f0f0f0;
  padding: 0.2em 0.4em;
  border-radius: 3px;
}

pre code {
  background: none;
  padding: 0;
}

table {
  border-collapse: collapse;
  width: 100%;
  margin: 1em 0;
}

th, td {
  border: 1px solid #d0d7de;
  padding: 0.5em 1em;
  text-align: left;
}

th {
  background: #f6f8fa;
  font-weight: 600;
}

/* Cover page layout */
.cover-page {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  min-height: 100vh;
  padding: 4rem 3rem;
  box-sizing: border-box;
  page-break-after: always;
  background: linear-gradient(180deg, #fafbfc 0%, #ffffff 100%);
}

.cover-title-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  text-align: center;
  padding: 2rem 0;
}

.cover-title {
  font-family: 'Inter', sans-serif;
  font-size: clamp(2.5rem, 6vw, 4rem);
  font-weight: 700;
  line-height: 1.15;
  margin: 0 0 1.5rem 0;
  color: #1a1a2e;
  letter-spacing: -0.02em;
}

.cover-subtitle {
  font-family: 'Inter', sans-serif;
  font-size: clamp(1.1rem, 2.5vw, 1.5rem);
  font-weight: 400;
  color: #57606a;
  margin: 0;
  line-height: 1.5;
}

.cover-footer {
  text-align: center;
  padding-bottom: 2rem;
}

.cover-logo {
  max-width: 260px;
  max-height: 100px;
  margin-bottom: 1.5rem;
}

.cover-meta {
  font-family: 'Inter', sans-serif;
  font-size: 0.95rem;
  color: #656d76;
}

.cover-version {
  font-weight: 600;
  color: #1a1a2e;
}

.cover-separator {
  margin: 0 0.75rem;
  color: #d0d7de;
}

.cover-date {
  color: #656d76;
}

@media print {
  .cover-page {
    height: 100vh;
    padding: 3rem 2rem;
    background: white;
  }
}
</style>

<div class="cover-page">
  <div class="cover-title-section">
    <h1 class="cover-title">Arch Ascent<br>User Guide</h1>
    <p class="cover-subtitle">Architectural Governance for Software Dependencies</p>
  </div>
  <div class="cover-footer">
    <img src="screenshots/logo.png" alt="Arch Ascent" class="cover-logo">
    <div class="cover-meta">
      <span class="cover-version">Version 1.0</span>
      <span class="cover-separator">|</span>
      <span class="cover-date">January 2026</span>
    </div>
  </div>
</div>
