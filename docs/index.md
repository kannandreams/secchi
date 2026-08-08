---
hide:
  - navigation
  - toc
---

<div class="lp-root" markdown="0">

<!-- ═══════════════════════════════════════════════════════════════ HERO ═══ -->

<section class="lp-hero">
  <h1 class="lp-title">Open Source Package Intelligence</h1>
  <p class="lp-subtitle">Package <span id="lp-typeword"></span><span class="lp-cursor">|</span> signals in one place.</p>
  <div class="lp-hero-actions">
    <a href="getting-started/" class="lp-btn lp-btn--primary">Get started</a>
    <a href="https://github.com/kannandreams/secchi" class="lp-btn lp-btn--secondary">GitHub</a>
  </div>
  <div class="lp-hero-meta">
    <span class="lp-badge"><code>uv tool install secchi</code></span>
    <a class="lp-license" href="https://github.com/kannandreams/secchi/blob/main/LICENSE">Apache 2.0</a>
  </div>
</section>

<!-- ══════════════════════════════════════════════════════════ FEATURES ═══ -->

<section class="lp-section">
  <h2 class="lp-section-title">// features</h2>
  <div class="lp-grid">
    <div class="lp-card">
      <div class="lp-card-icon">&#x25A0;</div>
      <h3>Interactive Dashboard</h3>
      <p>Rich TUI with health signals, adoption metrics, dependency graphs, and security advisories.</p>
    </div>
    <div class="lp-card">
      <div class="lp-card-icon">&#x25CB;</div>
      <h3>Cross-Registry Search</h3>
      <p>Find packages across PyPI, npm, crates.io, Homebrew, Go Modules, and CRAN from one command.</p>
    </div>
    <div class="lp-card">
      <div class="lp-card-icon">&#x25C6;</div>
      <h3>Package Comparison</h3>
      <p>Rank choices with evidence-based recommendations — Recommended, Acceptable, Caution, or Avoid.</p>
    </div>
    <div class="lp-card">
      <div class="lp-card-icon">&#x25B3;</div>
      <h3>Export &amp; Reports</h3>
      <p>Generate JSON, Markdown, and HTML reports for automation, docs, and stakeholders.</p>
    </div>
    <div class="lp-card">
      <div class="lp-card-icon">&#x25A3;</div>
      <h3>Workspace Monitoring</h3>
      <p>Monitor named projects with lazy loading. Configure once and revisit anytime.</p>
    </div>
    <div class="lp-card">
      <div class="lp-card-icon">&#x25CB;</div>
      <h3>MCP Server</h3>
      <p>Let AI coding agents inspect, search, compare, and check packages directly.</p>
    </div>
    <div class="lp-card">
      <div class="lp-card-icon">&#x2295;</div>
      <h3>Security Advisories</h3>
      <p>OSV.dev vulnerability lookup for the latest version across PyPI, npm, crates.io, Go, and CRAN.</p>
    </div>
  </div>
</section>

<!-- ═══════════════════════════════════════════════════════ ECOSYSTEMS ═══ -->

<section class="lp-section lp-section--alt">
  <h2 class="lp-section-title">// ecosystems</h2>
  <div class="lp-ecosystems">
    <div class="lp-eco"><img src="https://cdn.simpleicons.org/python" alt=""><span>PyPI</span></div>
    <div class="lp-eco"><img src="https://cdn.simpleicons.org/javascript" alt=""><span>npm</span></div>
    <div class="lp-eco"><img src="https://cdn.simpleicons.org/rust" alt=""><span>crates.io</span></div>
    <div class="lp-eco"><img src="https://cdn.simpleicons.org/homebrew" alt=""><span>Homebrew</span></div>
    <div class="lp-eco"><img src="https://cdn.simpleicons.org/go" alt=""><span>Go Modules</span></div>
    <div class="lp-eco"><img src="https://cdn.simpleicons.org/r" alt=""><span>CRAN</span></div>
  </div>
</section>

<!-- ════════════════════════════════════════════════════════════ INSTALL ═══ -->

<section class="lp-section">
  <h2 class="lp-section-title">// install</h2>
  <div class="lp-code-tabs">
    <div class="lp-code-tab">
      <span class="lp-code-label">uv</span>
      <code>uv tool install secchi</code>
    </div>
    <div class="lp-code-tab">
      <span class="lp-code-label">pipx</span>
      <code>pipx install secchi</code>
    </div>
    <div class="lp-code-tab">
      <span class="lp-code-label">pip</span>
      <code>pip install secchi</code>
    </div>
  </div>
</section>

<!-- ════════════════════════════════════════════════════════════ QUICK ═══ -->

<section class="lp-section lp-section--alt">
  <h2 class="lp-section-title">// quick start</h2>
  <div class="terminal-window">
    <div class="terminal-titlebar">
      <span class="terminal-dot terminal-dot--red"></span>
      <span class="terminal-dot terminal-dot--yellow"></span>
      <span class="terminal-dot terminal-dot--green"></span>
      <span class="terminal-title">secchi — package intelligence</span>
    </div>
    <div class="terminal-body">
      <div class="terminal-lines">
        <div class="terminal-line">
          <span class="terminal-prompt">~ $</span>
          <span class="terminal-cmd">secchi init</span>
        </div>
        <div class="terminal-line">
          <span class="terminal-prompt">~ $</span>
          <span class="terminal-cmd">secchi dashboard duckdb</span>
        </div>
        <div class="terminal-line">
          <span class="terminal-prompt">~ $</span>
          <span class="terminal-cmd">secchi compare pypi:duckdb pypi:polars</span>
        </div>
        <div class="terminal-line">
          <span class="terminal-prompt">~ $</span>
          <span class="terminal-cmd">secchi report duckdb --format html</span>
        </div>
        <div class="terminal-line">
          <span class="terminal-prompt">~ $</span>
          <span class="terminal-cmd">secchi mcp</span>
          <span class="terminal-cursor">&#9608;</span>
        </div>
      </div>
    </div>
  </div>
  <div class="lp-section-cta">
    <a href="commands/" class="lp-btn lp-btn--primary">All commands &rarr;</a>
  </div>
</section>

<!-- ════════════════════════════════════════════════════════════ FOOTER ═══ -->

<section class="lp-section lp-footer">
  <div class="lp-footer-grid">
    <div>
      <strong>Secchi</strong>
      <p>Open Source Package Intelligence.<br>Apache 2.0 licensed.</p>
    </div>
    <div>
      <strong>Docs</strong>
      <a href="getting-started/">Getting started</a>
      <a href="commands/">Commands</a>
      <a href="workspace/">Workspace</a>
      <a href="reports/">Reports</a>
      <a href="mcp/">MCP &amp; agents</a>
    </div>
    <div>
      <strong>Project</strong>
      <a href="https://github.com/kannandreams/secchi">GitHub</a>
      <a href="https://github.com/kannandreams/secchi/blob/main/LICENSE">License</a>
      <a href="https://github.com/kannandreams/secchi/blob/main/CHANGELOG.md">Changelog</a>
      <a href="contributing/">Contributing</a>
    </div>
  </div>
</section>

</div>

<script>
(function() {
  var words = ["health", "adoption", "security", "dependencies"];
  var el = document.getElementById("lp-typeword");
  if (!el) return;
  var i = 0;       // current word index
  var j = 0;       // current char index in word
  var typing = true;
  var speed = 60;  // ms per char

  function tick() {
    var word = words[i];
    if (typing) {
      el.textContent = word.slice(0, j + 1);
      j++;
      if (j >= word.length) {
        typing = false;
        setTimeout(tick, 1800);
        return;
      }
    } else {
      el.textContent = word.slice(0, j - 1);
      j--;
      if (j <= 0) {
        typing = true;
        i = (i + 1) % words.length;
        j = 0;
        el.textContent = "";
        setTimeout(tick, 200);
        return;
      }
    }
    setTimeout(tick, typing ? speed : 35);
  }

  tick();
})();
</script>
