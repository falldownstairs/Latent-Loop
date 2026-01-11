'use client';

import { useRef, useEffect } from 'react';
import { marked } from 'marked';

interface MarkdownRendererProps {
  content: string;
  animatingSection: string | null;
}

export function MarkdownRenderer({ content, animatingSection }: MarkdownRendererProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const html = marked.parse(content) as string;
    containerRef.current.innerHTML = html;

    // Apply glow animation to the target section
    if (animatingSection) {
      const headers = containerRef.current.querySelectorAll('h1, h2, h3');
      const search = animatingSection.toLowerCase().trim();

      headers.forEach((header) => {
        const text = header.textContent?.toLowerCase().trim() || '';
        
        let isMatch = false;
        if (text === search) {
          isMatch = true;
        } else if (text.startsWith(search) || search.startsWith(text)) {
          isMatch = true;
        } else if (text.includes(search) || search.includes(text)) {
          isMatch = true;
        }

        if (isMatch) {
          // Add glow to header
          header.classList.add('glow-green');

          // Add glow to section content
          let sibling = header.nextElementSibling;
          while (sibling && !['H1', 'H2', 'H3'].includes(sibling.tagName)) {
            sibling.classList.add('glow-green');
            sibling = sibling.nextElementSibling;
          }

          // Scroll to element
          const containerRect = containerRef.current!.parentElement?.getBoundingClientRect();
          const elementRect = header.getBoundingClientRect();
          if (containerRect) {
            const scrollContainer = containerRef.current!.parentElement;
            if (scrollContainer) {
              const scrollTop = elementRect.top - containerRect.top + scrollContainer.scrollTop - 60;
              scrollContainer.scrollTo({ top: scrollTop, behavior: 'smooth' });
            }
          }
        }
      });
    }
  }, [content, animatingSection]);

  return (
    <div 
      ref={containerRef} 
      className="markdown-content"
    />
  );
}
