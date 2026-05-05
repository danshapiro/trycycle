(function () {
  function escapeHtml(text) {
    return String(text)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function renderInline(text) {
    let html = escapeHtml(text);
    html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
    html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    html = html.replace(/\*([^*]+)\*/g, "<em>$1</em>");
    html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2">$1</a>');
    return html;
  }

  function render(markdown) {
    const lines = String(markdown).replace(/\r\n/g, "\n").split("\n");
    const html = [];
    const paragraph = [];
    let listType = null;
    let inCodeFence = false;
    let codeFenceLines = [];

    function flushParagraph() {
      if (!paragraph.length) {
        return;
      }
      html.push(`<p>${renderInline(paragraph.join(" "))}</p>`);
      paragraph.length = 0;
    }

    function flushList() {
      if (!listType) {
        return;
      }
      html.push(`</${listType}>`);
      listType = null;
    }

    function flushCodeFence() {
      if (!inCodeFence) {
        return;
      }
      html.push(`<pre><code>${escapeHtml(codeFenceLines.join("\n"))}</code></pre>`);
      codeFenceLines = [];
      inCodeFence = false;
    }

    for (const line of lines) {
      if (line.startsWith("```")) {
        flushParagraph();
        flushList();
        if (inCodeFence) {
          flushCodeFence();
        } else {
          inCodeFence = true;
          codeFenceLines = [];
        }
        continue;
      }

      if (inCodeFence) {
        codeFenceLines.push(line);
        continue;
      }

      const trimmed = line.trim();
      if (!trimmed) {
        flushParagraph();
        flushList();
        continue;
      }

      const heading = trimmed.match(/^(#{1,6})\s+(.*)$/);
      if (heading) {
        flushParagraph();
        flushList();
        const level = heading[1].length;
        html.push(`<h${level}>${renderInline(heading[2])}</h${level}>`);
        continue;
      }

      const blockQuote = trimmed.match(/^>\s?(.*)$/);
      if (blockQuote) {
        flushParagraph();
        flushList();
        html.push(`<blockquote><p>${renderInline(blockQuote[1])}</p></blockquote>`);
        continue;
      }

      const unordered = trimmed.match(/^[-*]\s+(.*)$/);
      if (unordered) {
        flushParagraph();
        if (listType !== "ul") {
          flushList();
          listType = "ul";
          html.push("<ul>");
        }
        html.push(`<li>${renderInline(unordered[1])}</li>`);
        continue;
      }

      const ordered = trimmed.match(/^\d+\.\s+(.*)$/);
      if (ordered) {
        flushParagraph();
        if (listType !== "ol") {
          flushList();
          listType = "ol";
          html.push("<ol>");
        }
        html.push(`<li>${renderInline(ordered[1])}</li>`);
        continue;
      }

      paragraph.push(trimmed);
    }

    flushParagraph();
    flushList();
    flushCodeFence();

    return html.join("\n");
  }

  window.MarkdownLite = { render };
})();
