(function () {
  const data = window.FOLIO_JOURNAL_DATA || { notes: [], stats: {}, sections: [], summaries: {} };
  data.summaries = data.summaries || { weekly: [], monthly: [] };
  const THEME_STORAGE_KEY = "folio-scribe-theme";
  const systemThemeQuery = window.matchMedia("(prefers-color-scheme: dark)");
  const state = {
    selectedDate: data.notes[0] ? data.notes[0].date : "",
    selectedEntry: "daily",
    currentMonth: data.notes[0] ? data.notes[0].date.substring(0, 7) : (() => {
      const d = new Date();
      return `${d.getFullYear()}-${(d.getMonth() + 1).toString().padStart(2, "0")}`;
    })(),
    query: "",
    visibleSection: "all",
  };

  const els = {
    notes: document.getElementById("note-list"),
    search: document.getElementById("search-input"),
    statNotes: document.getElementById("stat-notes"),
    statSections: document.getElementById("stat-sections"),
    statCompletion: document.getElementById("stat-completion"),
    statNotesLabel: document.getElementById("stat-notes-label"),
    statSectionsLabel: document.getElementById("stat-sections-label"),
    statCompletionLabel: document.getElementById("stat-completion-label"),
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

      const heading = trimmed.match(/^(#{2,6})\s+(.+)$/);
      if (heading) {
        const level = Math.min(Math.max(heading[1].length, 3), 4);
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
          /^#{2,6}\s+/.test(current) ||
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

  function summaryText(summary) {
    return [
      summary.id,
      summary.title,
      summary.model,
      summary.startDate,
      summary.endDate,
      (summary.tags || []).join(" "),
      summary.rawMarkdown || "",
    ]
      .join(" ")
      .toLowerCase();
  }

  function matchesQuery(text) {
    const query = state.query.trim().toLowerCase();
    return !query || String(text || "").toLowerCase().includes(query);
  }

  function filteredNotes() {
    return data.notes.filter((note) => matchesQuery(noteText(note)));
  }

  function summariesFor(kind) {
    return (data.summaries && data.summaries[kind]) || [];
  }

  function filteredSummaries(kind) {
    return summariesFor(kind).filter((summary) => matchesQuery(summaryText(summary)));
  }

  function selectedNote() {
    return filteredNotes().find((note) => note.date === state.selectedDate) || null;
  }

  function noteByDate(dateStr) {
    return data.notes.find((note) => note.date === dateStr) || null;
  }

  function summaryRange(summary) {
    if (!summary) return "-";
    if (summary.displayRange) return summary.displayRange;
    if (summary.startDate && summary.endDate) {
      return `${summary.startDate} - ${summary.endDate}`;
    }
    return summary.id || "-";
  }

  function monthKeyFromDate(value) {
    return String(value || "").slice(0, 7);
  }

  function dateInRange(dateStr, startDate, endDate) {
    if (!dateStr || !startDate || !endDate) return false;
    return dateStr >= startDate && dateStr <= endDate;
  }

  function summaryAnchorDate(summary) {
    if (!summary) return "";
    if (summary.anchorDate) return summary.anchorDate;
    const datedNotes = data.notes
      .map((note) => note.date)
      .filter((dateStr) => dateInRange(dateStr, summary.startDate, summary.endDate))
      .sort();
    if (datedNotes.length) return datedNotes[datedNotes.length - 1];
    return summary.endDate || summary.startDate || "";
  }

  function summaryForDate(kind, dateStr) {
    return filteredSummaries(kind).find((summary) => summaryAnchorDate(summary) === dateStr) || null;
  }

  function entriesForDate(dateStr) {
    const entries = [];
    const note = filteredNotes().find((item) => item.date === dateStr);
    const weekly = summaryForDate("weekly", dateStr);
    const monthly = summaryForDate("monthly", dateStr);

    if (note) {
      entries.push({
        type: "daily",
        label: "每日日志",
        title: note.title,
        meta: `${note.completedSectionCount || 0}/${note.sectionCount || 0} 已完成`,
        note,
      });
    }

    if (weekly) {
      const completed = weekly.completedSectionCount || 0;
      const total = weekly.sectionCount || 0;
      entries.push({
        type: "weekly",
        label: "每周总结",
        title: summaryRange(weekly),
        meta: total ? `${percent(completed, total)}% 完成` : `${weekly.dailyCount || 0} 个交易日`,
        summary: weekly,
      });
    }

    if (monthly) {
      const completed = monthly.completedSectionCount || 0;
      const total = monthly.sectionCount || 0;
      entries.push({
        type: "monthly",
        label: "每月总结",
        title: summaryRange(monthly) || monthly.id,
        meta: total ? `${percent(completed, total)}% 完成` : `${monthly.dailyCount || 0} 个交易日`,
        summary: monthly,
      });
    }

    return entries;
  }

  function allEntryDates() {
    const dates = new Set();
    filteredNotes().forEach((note) => dates.add(note.date));
    ["weekly", "monthly"].forEach((kind) => {
      filteredSummaries(kind).forEach((summary) => {
        const dateStr = summaryAnchorDate(summary);
        if (dateStr) dates.add(dateStr);
      });
    });
    return Array.from(dates).sort().reverse();
  }

  function currentEntry() {
    return entriesForDate(state.selectedDate).find((entry) => entry.type === state.selectedEntry) || null;
  }

  function normalizeSelection() {
    let entries = entriesForDate(state.selectedDate);
    if (!entries.length) {
      const dates = allEntryDates();
      state.selectedDate = dates[0] || "";
      entries = entriesForDate(state.selectedDate);
      if (state.selectedDate) state.currentMonth = state.selectedDate.substring(0, 7);
    }

    if (!entries.some((entry) => entry.type === state.selectedEntry)) {
      state.selectedEntry = entries[0] ? entries[0].type : "daily";
    }

    if (state.selectedEntry !== "daily") {
      state.visibleSection = "all";
    }
  }

  function currentMonthParts() {
    const [yearStr, monthStr] = state.currentMonth.split("-");
    let year = parseInt(yearStr, 10);
    let month = parseInt(monthStr, 10);
    if (Number.isNaN(year) || Number.isNaN(month)) {
      const date = new Date();
      year = date.getFullYear();
      month = date.getMonth() + 1;
      state.currentMonth = `${year}-${month.toString().padStart(2, "0")}`;
    }
    return { year, month };
  }

  function renderStats() {
    const stats = data.stats || {};
    els.generatedAt.textContent = `已生成 ${formatGeneratedAt(data.generatedAt)}`;

    const note = noteByDate(state.selectedDate) || selectedNote();
    const completed = note ? note.completedSectionCount || 0 : 0;
    const total = note ? note.sectionCount || 0 : 0;
    els.statNotes.textContent = stats.noteCount || 0;
    els.statSections.textContent = note ? `${completed}/${total}` : "0/0";
    els.statCompletion.textContent = note ? `${percent(completed, total)}%` : "0%";
    els.statNotesLabel.textContent = "交易日";
    els.statSectionsLabel.textContent = "已完成";
    els.statCompletionLabel.textContent = "完成率";
    els.statLatest.textContent = stats.latestDate || "-";
  }

  function renderNoteList() {
    const notes = filteredNotes();

    // Create quick lookup
    const notesByDate = {};
    notes.forEach((note) => {
      notesByDate[note.date] = note;
    });

    const weeklyByDate = {};
    const monthlyByDate = {};
    filteredSummaries("weekly").forEach((summary) => {
      const dateStr = summaryAnchorDate(summary);
      if (dateStr) weeklyByDate[dateStr] = summary;
    });
    filteredSummaries("monthly").forEach((summary) => {
      const dateStr = summaryAnchorDate(summary);
      if (dateStr) monthlyByDate[dateStr] = summary;
    });

    const { year, month } = currentMonthParts();

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

    if (allEntryDates().length === 0) {
      html += `<div class="empty-state" style="margin-top: 20px;">当前搜索条件下没有交易日志或总结。</div>`;
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
      const weekly = weeklyByDate[dateStr];
      const monthly = monthlyByDate[dateStr];
      const hasEntry = Boolean(note || weekly || monthly);
      const markers = [];
      if (note) markers.push('<span class="day-marker day-marker-daily" title="每日日志"></span>');
      if (weekly) markers.push('<span class="day-marker day-marker-weekly" title="每周总结"></span>');
      if (monthly) markers.push('<span class="day-marker day-marker-monthly" title="每月总结"></span>');

      if (hasEntry) {
        const active = dateStr === state.selectedDate ? " active" : "";
        const done = note ? note.completedSectionCount || 0 : 0;
        const total = note ? note.sectionCount || 0 : 0;
        const progress = note ? percent(done, total) : 0;
        const summaryClass = `${weekly ? " has-weekly" : ""}${monthly ? " has-monthly" : ""}`;
        const title = [
          note ? "每日日志" : "",
          weekly ? "每周总结" : "",
          monthly ? "每月总结" : "",
        ].filter(Boolean).join(" / ");
        
        let ringClass = "progress-none";
        if (!note) ringClass = "progress-summary";
        else if (progress === 100) ringClass = "progress-full";
        else if (progress > 0) ringClass = "progress-partial";

        html += `<button type="button" class="calendar-day has-entry ${note ? "has-note" : "has-summary"} ${ringClass}${summaryClass}${active}" data-date="${escapeHtml(dateStr)}" title="${escapeHtml(title)}">
          <span class="day-number">${d}</span>
          <span class="day-markers">${markers.join("")}</span>
        </button>`;
      } else {
        const isToday = today.getFullYear() === year && (today.getMonth() + 1) === month && today.getDate() === d;
        const todayClass = isToday ? " today" : "";
        html += `<div class="calendar-day${todayClass}"><span class="day-number">${d}</span></div>`;
      }
    }

    html += `</div></div>`;
    html += renderEntrySwitcher();
    els.notes.innerHTML = html;
  }

  function renderEntrySwitcher() {
    const entries = entriesForDate(state.selectedDate);
    if (!state.selectedDate) {
      return '<div class="entry-switcher empty-state">没有找到可查看的日志或总结。</div>';
    }
    if (!entries.length) {
      return `<div class="entry-switcher empty-state">${escapeHtml(state.selectedDate)} 没有可查看的日志或总结。</div>`;
    }

    return `<div class="entry-switcher" aria-label="Selected date entries">
      <div class="entry-switcher-header">
        <span>${escapeHtml(state.selectedDate)}</span>
        <strong>可查看内容</strong>
      </div>
      <div class="entry-options">
        ${entries.map((entry) => {
          const active = entry.type === state.selectedEntry ? " active" : "";
          return `<button type="button" class="${active}" data-entry="${escapeHtml(entry.type)}">
            <span class="entry-kind">${escapeHtml(entry.label)}</span>
            <strong>${escapeHtml(entry.title || entry.label)}</strong>
            <span class="entry-meta">${escapeHtml(entry.meta || "")}</span>
          </button>`;
        }).join("")}
      </div>
    </div>`;
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

  function renderSummaryContent(entry) {
    const summary = entry && entry.summary;
    const summaryLabel = entry && entry.type === "weekly" ? "周总结" : "月总结";
    els.sectionTabs.innerHTML = "";

    if (!summary) {
      els.selectedDate.textContent = "";
      els.selectedTitle.textContent = `没有${summaryLabel}`;
      els.selectedModel.textContent = "";
      els.selectedScores.textContent = "";
      els.selectedProgress.textContent = "0";
      els.selectedUpdated.textContent = "-";
      els.content.innerHTML = '<div class="empty-state">没有找到总结数据。</div>';
      return;
    }

    const completed = summary.completedSectionCount || 0;
    const total = summary.sectionCount || 0;
    els.selectedDate.textContent = summaryRange(summary);
    els.selectedTitle.textContent = summary.title || summary.id;
    els.selectedModel.textContent = summary.model ? `模型 ${summary.model}` : "模型未知";
    els.selectedScores.textContent = total ? `${percent(completed, total)}% 完成` : "";
    els.selectedProgress.textContent = `${summary.dailyCount || 0} 个交易日`;
    els.selectedUpdated.textContent = formatGeneratedAt(summary.generatedAt || data.generatedAt);
    const body = String(summary.rawMarkdown || "").replace(/^#\s+.+?(?:\r?\n){1,2}/, "");
    els.content.innerHTML = `<section class="section-block periodic-summary">${renderMarkdown(body)}</section>`;
  }

  function renderDailyContent(note) {
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

  function renderContent() {
    const entry = currentEntry();
    if (!entry) {
      els.selectedDate.textContent = state.selectedDate || "";
      els.selectedTitle.textContent = "没有内容";
      els.selectedModel.textContent = "";
      els.selectedScores.textContent = "";
      els.selectedProgress.textContent = "0";
      els.selectedUpdated.textContent = "-";
      els.sectionTabs.innerHTML = "";
      els.content.innerHTML = '<div class="empty-state">没有找到可查看的日志或总结。</div>';
      return;
    }

    if (entry.type === "daily") {
      renderDailyContent(entry.note);
      return;
    }

    renderSummaryContent(entry);
  }

  function scrollToContentStart() {
    const firstBlock = els.content ? els.content.querySelector(".section-block") : null;
    const target = firstBlock || els.content;
    if (!target) return;
    const topbar = document.querySelector(".topbar");
    const sectionTabs = els.sectionTabs;
    const offset = (topbar ? topbar.offsetHeight : 0) + (sectionTabs ? sectionTabs.offsetHeight : 0) + 18;
    const top = Math.max(0, window.scrollY + target.getBoundingClientRect().top - offset);
    window.scrollTo({ top, left: window.scrollX });
  }

  function render() {
    normalizeSelection();
    document.documentElement.dataset.view = state.selectedEntry;
    renderStats();
    renderContent();
    renderNoteList();
  }

  els.search.addEventListener("input", () => {
    state.query = els.search.value;
    const dates = allEntryDates();
    state.selectedDate = dates[0] || "";
    state.selectedEntry = "daily";
    if (state.selectedDate) state.currentMonth = state.selectedDate.substring(0, 7);
    state.visibleSection = "all";
    render();
  });

  els.notes.addEventListener("click", (event) => {
    const entryButton = event.target.closest(".entry-options button");
    if (entryButton) {
      state.selectedEntry = entryButton.dataset.entry || "daily";
      state.visibleSection = "all";
      render();
      return;
    }

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
    const button = event.target.closest(".calendar-day.has-entry");
    if (!button) return;
    state.selectedDate = button.dataset.date;
    const entries = entriesForDate(state.selectedDate);
    if (!entries.some((entry) => entry.type === state.selectedEntry)) {
      state.selectedEntry = entries[0] ? entries[0].type : "daily";
    }
    state.visibleSection = "all";
    render();
  });

  els.sectionTabs.addEventListener("click", (event) => {
    const button = event.target.closest("button");
    if (!button) return;
    const nextSection = button.dataset.section || "all";
    if (nextSection === state.visibleSection) return;
    state.visibleSection = nextSection;
    renderContent();
    window.requestAnimationFrame(scrollToContentStart);
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
