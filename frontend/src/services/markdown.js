import DOMPurify from "dompurify";
import hljs from "highlight.js/lib/common";
import katex from "katex";
import MarkdownIt from "markdown-it";
import texmath from "markdown-it-texmath";

const md = new MarkdownIt({
  html: true,
  linkify: true,
  breaks: true,
  highlight: (str, lang) => {
    const normalizedLang = String(lang || "").trim().toLowerCase();
    if (normalizedLang && hljs.getLanguage(normalizedLang)) {
      return `<pre data-language="${md.utils.escapeHtml(normalizedLang)}"><code class=\"hljs language-${md.utils.escapeHtml(normalizedLang)}\">${hljs.highlight(str, { language: normalizedLang }).value}</code></pre>`;
    }
    return `<pre data-language="text"><code class=\"hljs language-text\">${md.utils.escapeHtml(str)}</code></pre>`;
  },
}).use(texmath, {
  engine: katex,
  delimiters: ["dollars", "brackets", "beg_end"],
  katexOptions: {
    throwOnError: false,
    strict: "warn",
    output: "htmlAndMathml",
    trust: false,
  },
});

function normalizeImageSrc(src) {
  const value = String(src || "").trim();
  if (!value) return value;

  // Keep absolute/data/blob URLs untouched.
  if (/^([a-z][a-z\d+\-.]*:)?\/\//i.test(value) || value.startsWith("data:") || value.startsWith("blob:")) {
    return value;
  }

  // Convert markdown relative assets paths to a stable public directory.
  if (/^(?:\.\/|\/)?assets\//i.test(value)) {
    return `/${value.replace(/^(?:\.\/|\/)?assets\//i, "wiki-assets/")}`;
  }

  if (/^wiki-assets\//i.test(value)) {
    return `/${value}`;
  }

  return value;
}

function normalizeLinkHref(href) {
  const value = String(href || "").trim();
  if (!value) return value;

  // Keep anchors and site-relative links as-is.
  if (value.startsWith("#") || value.startsWith("/") || value.startsWith("./") || value.startsWith("../")) {
    return value;
  }

  // Keep explicit protocols untouched.
  if (/^[a-z][a-z\d+\-.]*:/i.test(value) || value.startsWith("//")) {
    return value;
  }

  // Support markdown links like [baidu](www.baidu.com) and [x](baidu.com).
  if (/^www\./i.test(value) || /^[a-z\d-]+(\.[a-z\d-]+)+([/?#].*)?$/i.test(value)) {
    return `https://${value}`;
  }

  return value;
}

const defaultImageRenderer =
  md.renderer.rules.image ||
  ((tokens, idx, options, _env, self) => self.renderToken(tokens, idx, options));

md.renderer.rules.image = (tokens, idx, options, env, self) => {
  const token = tokens[idx];
  const srcIndex = token.attrIndex("src");
  if (srcIndex >= 0) {
    const src = token.attrs[srcIndex][1];
    token.attrs[srcIndex][1] = normalizeImageSrc(src);
  }
  return defaultImageRenderer(tokens, idx, options, env, self);
};

const defaultLinkOpenRenderer =
  md.renderer.rules.link_open ||
  ((tokens, idx, options, _env, self) => self.renderToken(tokens, idx, options));

md.renderer.rules.link_open = (tokens, idx, options, env, self) => {
  const token = tokens[idx];
  const hrefIndex = token.attrIndex("href");
  if (hrefIndex >= 0) {
    token.attrs[hrefIndex][1] = normalizeLinkHref(token.attrs[hrefIndex][1]);
  }

  if (token.attrIndex("target") < 0) {
    token.attrPush(["target", "_blank"]);
  } else {
    token.attrs[token.attrIndex("target")][1] = "_blank";
  }
  if (token.attrIndex("rel") < 0) {
    token.attrPush(["rel", "noopener noreferrer"]);
  } else {
    token.attrs[token.attrIndex("rel")][1] = "noopener noreferrer";
  }

  return defaultLinkOpenRenderer(tokens, idx, options, env, self);
};

const markdownSanitizeConfig = {
  USE_PROFILES: { html: true, mathMl: true, svg: true },
  ADD_ATTR: ["style", "target", "rel"],
  FORBID_TAGS: ["script", "style", "iframe", "object", "embed", "form", "input", "button", "textarea", "select", "option"],
};

function isEscapedDollar(source, index) {
  let slashCount = 0;
  for (let cursor = index - 1; cursor >= 0 && source[cursor] === "\\"; cursor -= 1) {
    slashCount += 1;
  }
  return slashCount % 2 === 1;
}

function normalizeLatexWhitespaceInSegment(segment) {
  let result = "";
  let index = 0;

  while (index < segment.length) {
    if (segment[index] !== "$" || isEscapedDollar(segment, index)) {
      result += segment[index];
      index += 1;
      continue;
    }

    const delimiterLength = segment[index + 1] === "$" && !isEscapedDollar(segment, index + 1) ? 2 : 1;
    let closingIndex = -1;
    let cursor = index + delimiterLength;

    while (cursor < segment.length) {
      if (segment[cursor] !== "$" || isEscapedDollar(segment, cursor)) {
        cursor += 1;
        continue;
      }

      const currentDelimiterLength =
        segment[cursor + 1] === "$" && !isEscapedDollar(segment, cursor + 1) ? 2 : 1;
      if (currentDelimiterLength !== delimiterLength) {
        cursor += currentDelimiterLength;
        continue;
      }

      closingIndex = cursor;
      break;
    }

    if (closingIndex < 0) {
      result += segment[index];
      index += 1;
      continue;
    }

    const inner = segment.slice(index + delimiterLength, closingIndex);
    if (delimiterLength === 1 && inner.includes("\n")) {
      result += segment.slice(index, closingIndex + delimiterLength);
      index = closingIndex + delimiterLength;
      continue;
    }

    const normalizedInner = inner.replace(/^[ \t]+/, "").replace(/[ \t]+$/, "");
    result += "$".repeat(delimiterLength) + normalizedInner + "$".repeat(delimiterLength);
    index = closingIndex + delimiterLength;
  }

  return result;
}

function normalizeLatexWhitespace(content) {
  const source = String(content || "");
  const protectedCodePattern = /(```[\s\S]*?```|~~~[\s\S]*?~~~|`[^`\n]*`)/g;
  let result = "";
  let lastIndex = 0;
  let match = protectedCodePattern.exec(source);

  while (match) {
    result += normalizeLatexWhitespaceInSegment(source.slice(lastIndex, match.index));
    result += match[0];
    lastIndex = match.index + match[0].length;
    match = protectedCodePattern.exec(source);
  }

  result += normalizeLatexWhitespaceInSegment(source.slice(lastIndex));
  return result;
}

function normalizeRenderedHtml(html) {
  if (typeof DOMParser === "undefined") {
    return html;
  }

  const parser = new DOMParser();
  const doc = parser.parseFromString(`<div data-md-root="1">${html}</div>`, "text/html");
  const root = doc.querySelector("[data-md-root='1']");
  if (!root) {
    return html;
  }

  root.querySelectorAll("img").forEach((node) => {
    const src = node.getAttribute("src");
    if (src) {
      node.setAttribute("src", normalizeImageSrc(src));
    }
  });

  root.querySelectorAll("a").forEach((node) => {
    const href = node.getAttribute("href");
    if (href) {
      node.setAttribute("href", normalizeLinkHref(href));
    }
    node.setAttribute("target", "_blank");
    node.setAttribute("rel", "noopener noreferrer");
  });

  return root.innerHTML;
}

export function renderMarkdown(content) {
  const rendered = md.render(normalizeLatexWhitespace(content));
  if (typeof window === "undefined") {
    return rendered;
  }
  const normalized = normalizeRenderedHtml(DOMPurify.sanitize(rendered, markdownSanitizeConfig));
  return DOMPurify.sanitize(normalized, markdownSanitizeConfig);
}

export function renderInlineMarkdown(content) {
  const rendered = md.renderInline(normalizeLatexWhitespace(content));
  if (typeof window === "undefined") {
    return rendered;
  }
  const normalized = normalizeRenderedHtml(DOMPurify.sanitize(rendered, markdownSanitizeConfig));
  return DOMPurify.sanitize(normalized, markdownSanitizeConfig);
}
