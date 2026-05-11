(function () {
  const data = window.FOLIO_JOURNAL_DATA || { notes: [], stats: {}, sections: [] };
  const THEME_STORAGE_KEY = "folio-scribe-theme";
  const systemThemeQuery = window.matchMedia("(prefers-color-scheme: dark)");
  const state = {
    selectedDate: data.notes[0] ? data.notes[0].date : "",
    currentMonth: data.notes[0] ? data.notes[0].date.substring(0, 7) : (() => {
      const d = new Date();
      return `${d.getFullYear()}-${(d.getMonth() + 1).toString().padStart(2, "0")}`;
    })(),
    query: "",
    filter: "all",
    visibleSection: "all",
  };

  const els = {
    notes: document.getElementById("note-list"),
    search: document.getElementById("search-input"),
    statNotes: document.getElementById("stat-notes"),
    statSections: document.getElementById("stat-sections"),
    statCompletion: document.getElementById("stat-completion"),
    statLatest: document.getElementById("stat-latest"),
    generatedAt: document.getElementById("generated-at"),
    selectedDate: document.getElementById("selected-date"),
    selectedTitle: document.getElementById("selected-title"),
    selectedModel: document.getElementById("selected-model"),
    selectedScores: document.getElementById("selected-scores"),
    selectedProgress: document.getElementById("selected-progress"),
    selectedUpdated: document.getElementById("selected-updated"),
    sectionTabs: document.getElementById("section-tabs"),
    content: document.getElementById("journal-content"),
    themeToggle: document.getElementById("theme-toggle"),
  };

  function loadThemeOption() {
    try {
      const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
      if (stored === "light" || stored === "dark") return stored;
      if (stored === "system") return systemThemeQuery.matches ? "dark" : "light";
    } catch (_error) {
      return systemThemeQuery.matches ? "dark" : "light";
    }
    return systemThemeQuery.matches ? "dark" : "light";
  }

  function saveThemeOption(option) {
    try {
      window.localStorage.setItem(THEME_STORAGE_KEY, option);
    } catch (_error) {
      // Ignore private-mode storage failures; the visual state still updates for this session.
    }
  }

  function resolveTheme(option) {
    return option === "dark" ? "dark" : "light";
  }

  function applyTheme(option) {
    const resolved = resolveTheme(option);
    document.documentElement.dataset.theme = resolved;
    document.documentElement.dataset.themeMode = resolved;
    if (els.themeToggle) {
      const isDark = resolved === "dark";
      els.themeToggle.classList.toggle("is-dark", isDark);
      els.themeToggle.setAttribute("aria-pressed", isDark ? "true" : "false");
      els.themeToggle.setAttribute("aria-label", `Switch to ${isDark ? "light" : "dark"} theme`);
      els.themeToggle.title = `Switch to ${isDark ? "Light" : "Dark"}`;
    }
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function safeClass(value) {
    return String(value || "").replace(/[^a-z0-9_-]/gi, "");
  }

  function percent(done, total) {
    if (!total) return 0;
    return Math.round((Number(done || 0) / Number(total || 1)) * 100);
  }

  function formatGeneratedAt(value) {
    if (!value) return "-";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "-";
    return new Intl.DateTimeFormat("zh-CN", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }).format(date);
  }

  function inlineMarkdown(value) {
    let html = escapeHtml(value);
    html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g, '<a href="$2" rel="noreferrer">$1</a>');
    html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
    html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    html = html.replace(/\*([^*]+)\*/g, "<em>$1</em>");
    return html;
  }

  function splitTableRow(line) {
    return line
      .trim()
      .replace(/^\|/, "")
      .replace(/\|$/, "")
      .split("|")
      .map((cell) => cell.trim());
  }

  function isTableSeparator(line) {
    return /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(line);
  }

  function renderTable(lines, start) {
    const header = splitTableRow(lines[start]);
    const rows = [];
    let index = start + 2;
    while (index < lines.length && lines[index].includes("|") && lines[index].trim() !== "") {
      rows.push(splitTableRow(lines[index]));
      index += 1;
    }

    const head = header.map((cell) => `<th>${inlineMarkdown(cell)}</th>`).join("");
    const body = rows
      .map((row) => `<tr>${row.map((cell) => `<td>${inlineMarkdown(cell)}</td>`).join("")}</tr>`)
      .join("");
    return {
      html: `<div class="table-wrap"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`,
      next: index,
    };
  }

  function renderMarkdown(markdown) {
    const lines = String(markdown || "").split(/\r?\n/);
    const parts = [];
    let index = 0;
    let inCode = false;
    let codeLines = [];

    function flushCode() {
      parts.push(`<pre><code>${escapeHtml(codeLines.join("\n"))}</code></pre>`);
      codeLines = [];
    }

    while (index < lines.length) {
      const line = lines[index];
      const trimmed = line.trim();

      if (trimmed.startsWith("```")) {
        if (inCode) {
          flushCode();
          inCode = false;
        } else {
          inCode = true;
        }
        index += 1;
        continue;
      }

      if (inCode) {
        codeLines.push(line);
        index += 1;
        continue;
      }

      if (!trimmed) {
        index += 1;
        continue;
      }

      if (trimmed === "---") {
        parts.push("<hr>");
        index += 1;
        continue;
      }

      if (line.includes("|") && index + 1 < lines.length && isTableSeparator(lines[index + 1])) {
        const rendered = renderTable(lines, index);
        parts.push(rendered.html);
        index = rendered.next;
        continue;
      }

      const heading = trimmed.match(/^(#{3,6})\s+(.+)$/);
      if (heading) {
        const level = Math.min(heading[1].length, 4);
        parts.push(`<h${level}>${inlineMarkdown(heading[2])}</h${level}>`);
        index += 1;
        continue;
      }

      if (trimmed.startsWith(">")) {
        const quoteLines = [];
        while (index < lines.length && lines[index].trim().startsWith(">")) {
          quoteLines.push(lines[index].trim().replace(/^>\s?/, ""));
          index += 1;
        }
        parts.push(`<blockquote>${quoteLines.map(inlineMarkdown).join("<br>")}</blockquote>`);
        continue;
      }

      if (/^[-*]\s+/.test(trimmed)) {
        const items = [];
        while (index < lines.length && /^[-*]\s+/.test(lines[index].trim())) {
          const item = lines[index].trim().replace(/^[-*]\s+/, "");
          const task = item.match(/^\[([ xX])\]\s+(.+)$/);
          if (task) {
            const checked = task[1].trim() ? "checked" : "";
            items.push(`<li><input type="checkbox" disabled ${checked}>${inlineMarkdown(task[2])}</li>`);
          } else {
            items.push(`<li>${inlineMarkdown(item)}</li>`);
          }
          index += 1;
        }
        parts.push(`<ul>${items.join("")}</ul>`);
        continue;
      }

      if (/^\d+\.\s+/.test(trimmed)) {
        const items = [];
        while (index < lines.length && /^\d+\.\s+/.test(lines[index].trim())) {
          items.push(`<li>${inlineMarkdown(lines[index].trim().replace(/^\d+\.\s+/, ""))}</li>`);
          index += 1;
        }
        parts.push(`<ol>${items.join("")}</ol>`);
        continue;
      }

      const paragraph = [];
      while (index < lines.length) {
        const current = lines[index].trim();
        if (
          !current ||
          current.startsWith("```") ||
          current.startsWith(">") ||
          current === "---" ||
          /^#{3,6}\s+/.test(current) ||
          /^[-*]\s+/.test(current) ||
          /^\d+\.\s+/.test(current) ||
          (lines[index].includes("|") && index + 1 < lines.length && isTableSeparator(lines[index + 1]))
        ) {
          break;
        }
        paragraph.push(current);
        index += 1;
      }
      parts.push(`<p>${inlineMarkdown(paragraph.join(" "))}</p>`);
    }

    if (inCode) {
      flushCode();
    }
    return parts.join("\n");
  }

  function noteText(note) {
    return [
      note.date,
      note.title,
      note.model,
      note.tags.join(" "),
      note.sections.map((section) => `${section.title} ${section.content}`).join(" "),
    ]
      .join(" ")
      .toLowerCase();
  }

  function filteredNotes() {
    const query = state.query.trim().toLowerCase();
    return data.notes.filter((note) => {
      const matchesQuery = !query || noteText(note).includes(query);
      const matchesFilter =
        state.filter === "all" ||
        note.sections.some((section) => section.key === state.filter && !section.pending);
      return matchesQuery && matchesFilter;
    });
  }

  function selectedNote() {
    return data.notes.find((note) => note.date === state.selectedDate) || filteredNotes()[0] || data.notes[0];
  }

  function renderStats() {
    const stats = data.stats || {};
    const completed = stats.completedSectionCount || 0;
    const total = stats.sectionCount || 0;
    els.statNotes.textContent = stats.noteCount || 0;
    els.statSections.textContent = `${completed}/${total}`;
    els.statCompletion.textContent = `${percent(completed, total)}%`;
    els.statLatest.textContent = stats.latestDate || "-";
    els.generatedAt.textContent = `已生成 ${formatGeneratedAt(data.generatedAt)}`;
  }

  function renderNoteList() {
    const notes = filteredNotes();
    
    // Create quick lookup
    const notesByDate = {};
    notes.forEach((note) => {
      notesByDate[note.date] = note;
    });

    const [yearStr, monthStrNum] = state.currentMonth.split("-");
    let year = parseInt(yearStr, 10);
    let month = parseInt(monthStrNum, 10);
    
    // Ensure valid year/month fallback
    if (isNaN(year) || isNaN(month)) {
      const d = new Date();
      year = d.getFullYear();
      month = d.getMonth() + 1;
      state.currentMonth = `${year}-${month.toString().padStart(2, "0")}`;
    }

    const monthDate = new Date(year, month - 1, 1);
    const monthName = monthDate.toLocaleString("zh-CN", { year: "numeric", month: "long" });
    
    const daysInMonth = new Date(year, month, 0).getDate();
    const firstDay = new Date(year, month - 1, 1).getDay();
    const startOffset = firstDay === 0 ? 6 : firstDay - 1;
    const today = new Date();

    // Month Navigation UI
    let html = `
      <div class="calendar-header">
        <button type="button" class="calendar-nav prev-month" aria-label="Previous month">
          <svg viewBox="0 0 24 24"><path d="m15 18-6-6 6-6"></path></svg>
        </button>
        <div class="calendar-month-name">${escapeHtml(monthName)}</div>
        <button type="button" class="calendar-nav next-month" aria-label="Next month">
          <svg viewBox="0 0 24 24"><path d="m9 18 6-6-6-6"></path></svg>
        </button>
      </div>`;

    if (notes.length === 0) {
      html += `<div class="empty-state" style="margin-top: 20px;">当前筛选条件下没有交易日志。</div>`;
    }

    html += `
      <div class="calendar-month">
        <div class="calendar-weekdays">
          <span>一</span><span>二</span><span>三</span><span>四</span><span>五</span><span>六</span><span>日</span>
        </div>
        <div class="calendar-grid">`;

    for (let i = 0; i < startOffset; i++) {
      html += `<div class="calendar-day empty"></div>`;
    }

    for (let d = 1; d <= daysInMonth; d++) {
      const dateStr = `${year}-${month.toString().padStart(2, "0")}-${d.toString().padStart(2, "0")}`;
      const note = notesByDate[dateStr];

      if (note) {
        const active = note.date === state.selectedDate ? " active" : "";
        const done = note.completedSectionCount || 0;
        const total = note.sectionCount || 0;
        const progress = percent(done, total);
        
        let ringClass = "progress-none";
        if (progress === 100) ringClass = "progress-full";
        else if (progress > 0) ringClass = "progress-partial";

        html += `<button type="button" class="calendar-day has-note ${ringClass}${active}" data-date="${escapeHtml(dateStr)}" title="${escapeHtml(note.title)}">
          <span class="day-number">${d}</span>
          <span class="day-indicator"></span>
        </button>`;
      } else {
        const isToday = today.getFullYear() === year && (today.getMonth() + 1) === month && today.getDate() === d;
        const todayClass = isToday ? " today" : "";
        html += `<div class="calendar-day${todayClass}"><span class="day-number">${d}</span></div>`;
      }
    }

    html += `</div></div>`;
    els.notes.innerHTML = html;
  }

  function renderSectionTabs(note) {
    const tabs = [{ key: "all", label: "全部", pending: false }].concat(
      note.sections.map((section) => ({
        key: section.key,
        label: section.time ? `${section.time} ${section.label}` : section.label,
        pending: section.pending,
      }))
    );
    els.sectionTabs.innerHTML = tabs
      .map((tab) => {
        const active = tab.key === state.visibleSection ? " active" : "";
        const pending = tab.pending ? " is-pending" : "";
        return `<button type="button" class="${active}${pending}" data-section="${escapeHtml(tab.key)}">${escapeHtml(tab.label)}</button>`;
      })
      .join("");
  }

  function renderContent() {
    const note = selectedNote();
    if (!note) {
      els.selectedDate.textContent = "";
      els.selectedTitle.textContent = "没有日志";
      els.selectedModel.textContent = "";
      els.selectedScores.textContent = "";
      els.selectedProgress.textContent = "0/0";
      els.selectedUpdated.textContent = "-";
      els.content.innerHTML = '<div class="empty-state">没有找到交易日志数据。</div>';
      els.sectionTabs.innerHTML = "";
      return;
    }

    state.selectedDate = note.date;
    const done = note.completedSectionCount || 0;
    const total = note.sectionCount || 0;
    els.selectedDate.textContent = note.date;
    els.selectedTitle.textContent = note.title;
    els.selectedModel.textContent = note.model ? `模型 ${note.model}` : "模型未知";
    const scoreBits = [];
    if (note.planScore) scoreBits.push(`计划 ${note.planScore}`);
    if (note.disciplineScore) scoreBits.push(`纪律 ${note.disciplineScore}`);
    els.selectedScores.textContent = scoreBits.join(" / ") || `${percent(done, total)}% 完成`;
    els.selectedProgress.textContent = `${done}/${total}`;
    els.selectedUpdated.textContent = formatGeneratedAt(data.generatedAt);

    if (state.visibleSection !== "all" && !note.sections.some((section) => section.key === state.visibleSection)) {
      state.visibleSection = "all";
    }
    renderSectionTabs(note);

    const visible = note.sections.filter(
      (section) => state.visibleSection === "all" || section.key === state.visibleSection
    );
    els.content.innerHTML = visible
      .map((section) => {
        const badge = section.pending
          ? '<span class="badge pending">待更新</span>'
          : `<span class="badge">${escapeHtml(section.label)}</span>`;
        const time = section.time ? `<span class="time">${escapeHtml(section.time)}</span>` : "";
        const body = section.pending ? '<p class="empty-state">待更新。</p>' : renderMarkdown(section.content);
        return `<section class="section-block section-${safeClass(section.key)}">
          <header class="section-heading">
            <div class="section-kicker">${time}${badge}</div>
            <h3>${escapeHtml(section.title)}</h3>
          </header>
          ${body}
        </section>`;
      })
      .join("");
  }

  function render() {
    renderStats();
    renderContent();
    renderNoteList();
  }

  document.querySelectorAll(".filter-tabs button").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".filter-tabs button").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      state.filter = button.dataset.filter || "all";
      const notes = filteredNotes();
      state.selectedDate = notes[0] ? notes[0].date : "";
      if (notes[0]) state.currentMonth = notes[0].date.substring(0, 7);
      state.visibleSection = "all";
      render();
    });
  });

  els.search.addEventListener("input", () => {
    state.query = els.search.value;
    const notes = filteredNotes();
    state.selectedDate = notes[0] ? notes[0].date : "";
    if (notes[0]) state.currentMonth = notes[0].date.substring(0, 7);
    state.visibleSection = "all";
    render();
  });

  els.notes.addEventListener("click", (event) => {
    // Handle month navigation
    const prevBtn = event.target.closest(".prev-month");
    const nextBtn = event.target.closest(".next-month");
    
    if (prevBtn || nextBtn) {
      let [y, m] = state.currentMonth.split("-").map(Number);
      if (prevBtn) m--;
      if (nextBtn) m++;
      if (m < 1) { m = 12; y--; }
      if (m > 12) { m = 1; y++; }
      state.currentMonth = `${y}-${m.toString().padStart(2, "0")}`;
      renderNoteList();
      return;
    }

    // Handle date selection
    const button = event.target.closest(".calendar-day.has-note");
    if (!button) return;
    state.selectedDate = button.dataset.date;
    state.visibleSection = "all";
    render();
  });

  els.sectionTabs.addEventListener("click", (event) => {
    const button = event.target.closest("button");
    if (!button) return;
    state.visibleSection = button.dataset.section || "all";
    render();
  });

  if (els.themeToggle) {
    els.themeToggle.addEventListener("click", () => {
      const option = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
      saveThemeOption(option);
      applyTheme(option);
    });
  }

  applyTheme(loadThemeOption());
  render();
})();
