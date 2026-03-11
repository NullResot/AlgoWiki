import hljs from "highlight.js/lib/common";
import MarkdownIt from "markdown-it";

const md = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true,
  highlight: (str, lang) => {
    if (lang && hljs.getLanguage(lang)) {
      return `<pre><code class=\"hljs\">${hljs.highlight(str, { language: lang }).value}</code></pre>`;
    }
    return `<pre><code class=\"hljs\">${md.utils.escapeHtml(str)}</code></pre>`;
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

export function renderMarkdown(content) {
  return md.render(content || "");
}
