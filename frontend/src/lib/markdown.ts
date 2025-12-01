import { marked } from 'marked';

/**
 * Custom extension to handle citations in the format [cite: 1, 2]
 * It renders them as superscript numbers: <sup>[1, 2]</sup>
 */
const citationExtension = {
  name: 'citation',
  level: 'inline' as const,
  
  // Determines where the tokenizer should start looking for our pattern
  start(src: string) {
    const match = src.match(/\[cite:/);
    return match ? match.index : undefined;
  },

  // Parsing logic: matches the [cite: ...] pattern
  tokenizer(src: string) {
    // Regex to match [cite: 123] or [cite: 1, 2]
    const rule = /^\[cite: ?([0-9, ]+)\]/;
    const match = rule.exec(src);
    
    if (match) {
      return {
        type: 'citation',
        raw: match[0],         // The full text, e.g., "[cite: 1]"
        text: match[1].trim()  // The numbers, e.g., "1"
      };
    }
    return undefined;
  },

  // Rendering logic: converts the token to HTML
  renderer(token: any) {
    return `<sup class="citation">[${token.text}]</sup>`;
  }
};

// Apply the extension to marked
marked.use({ extensions: [citationExtension] });

// Export a function to render markdown
export default function renderMarkdown(content: string): string {
  if (!content) return '';
  // Cast to string to handle potential Promise return types in some marked versions
  return marked.parse(content) as string;
}