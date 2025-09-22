#!/usr/bin/env python3
"""
IBDP Extended Essay Word Counter for LaTeX files

This script counts words in LaTeX files according to IBDP Extended Essay guidelines:
- Maximum 4,000 words for the main text
- Excludes: abstract, bibliography, footnotes, title page, table of contents
- Includes: introduction, body, conclusion, quotations

Usage: python3 count_words.py Paper/main.tex
"""

import re
import sys
import argparse
from pathlib import Path

def remove_latex_commands(text):
    """Remove LaTeX commands and environments that don't contribute to word count."""
    
    # Remove comments
    text = re.sub(r'%.*', '', text)
    
    # Remove preamble (everything before \begin{document})
    text = re.sub(r'.*?\\begin\{document\}', '', text, flags=re.DOTALL)
    
    # Remove \end{document} and everything after
    text = re.sub(r'\\end\{document\}.*', '', text, flags=re.DOTALL)
    
    # Remove title page
    text = re.sub(r'\\begin\{titlepage\}.*?\\end\{titlepage\}', '', text, flags=re.DOTALL)
    
    # Remove table of contents
    text = re.sub(r'\\tableofcontents', '', text)
    
    # Remove bibliography section and references
    text = re.sub(r'\\section\{References\}.*', '', text, flags=re.DOTALL)
    text = re.sub(r'\\nocite\{.*?\}', '', text)
    text = re.sub(r'\\bibliographystyle\{.*?\}', '', text)
    text = re.sub(r'\\bibliography\{.*?\}', '', text)
    
    # Remove appendices section if it exists
    text = re.sub(r'\\section\{Appendices\}.*', '', text, flags=re.DOTALL)
    
    # Remove figures and tables (captions are kept as they may contain substantive content)
    text = re.sub(r'\\begin\{figure\}.*?\\end\{figure\}', '', text, flags=re.DOTALL)
    text = re.sub(r'\\begin\{table\}.*?\\end\{table\}', '', text, flags=re.DOTALL)
    text = re.sub(r'\\begin\{tikzpicture\}.*?\\end\{tikzpicture\}', '', text, flags=re.DOTALL)
    
    # Remove code listings
    text = re.sub(r'\\begin\{lstlisting\}.*?\\end\{lstlisting\}', '', text, flags=re.DOTALL)
    
    # Remove LaTeX commands but keep their content where appropriate
    # Remove formatting commands but keep text
    text = re.sub(r'\\textbf\{([^}]*)\}', r'\1', text)
    text = re.sub(r'\\textit\{([^}]*)\}', r'\1', text)
    text = re.sub(r'\\emph\{([^}]*)\}', r'\1', text)
    text = re.sub(r'\\cite[tp]?\{[^}]*\}', '', text)  # Remove citations
    
    # Remove section commands but keep titles
    text = re.sub(r'\\section\*?\{([^}]*)\}', r'\1', text)
    text = re.sub(r'\\subsection\*?\{([^}]*)\}', r'\1', text)
    text = re.sub(r'\\subsubsection\*?\{([^}]*)\}', r'\1', text)
    
    # Remove other LaTeX commands
    text = re.sub(r'\\[a-zA-Z]+\*?\{[^}]*\}', '', text)
    text = re.sub(r'\\[a-zA-Z]+\*?', '', text)
    
    # Remove remaining braces
    text = re.sub(r'[{}]', '', text)
    
    # Remove mathematical expressions
    text = re.sub(r'\$.*?\$', '', text)
    text = re.sub(r'\\begin\{equation\}.*?\\end\{equation\}', '', text, flags=re.DOTALL)
    text = re.sub(r'\\begin\{align\}.*?\\end\{align\}', '', text, flags=re.DOTALL)
    
    # Clean up whitespace
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    
    return text

def count_words(text):
    """Count words in cleaned text."""
    if not text.strip():
        return 0
    
    # Split on whitespace and filter out empty strings
    words = [word for word in text.split() if word.strip()]
    return len(words)

def count_latex_file(filepath):
    """Count words in a LaTeX file according to IBDP EE guidelines."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"Error: File '{filepath}' not found.")
        return None
    except Exception as e:
        print(f"Error reading file: {e}")
        return None
    
    # Clean the content
    cleaned_content = remove_latex_commands(content)
    
    # Count words
    word_count = count_words(cleaned_content)
    
    return word_count, cleaned_content

def main():
    parser = argparse.ArgumentParser(
        description="Count words in LaTeX files for IBDP Extended Essay",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 count_words.py Paper/main.tex
  python3 count_words.py Paper/main.tex --show-text

The script excludes:
- Abstract, bibliography, footnotes
- Title page, table of contents
- Figures, tables, code listings
- LaTeX commands and formatting

The 4,000-word limit applies to the main text only.
        """
    )
    
    parser.add_argument('file', help='Path to the LaTeX file to analyze')
    parser.add_argument('--show-text', action='store_true', 
                       help='Show the cleaned text that was counted')
    parser.add_argument('--debug', action='store_true',
                       help='Show detailed processing information')
    
    args = parser.parse_args()
    
    filepath = Path(args.file)
    if not filepath.exists():
        print(f"Error: File '{filepath}' does not exist.")
        sys.exit(1)
    
    result = count_latex_file(filepath)
    if result is None:
        sys.exit(1)
    
    word_count, cleaned_text = result
    
    print(f"File: {filepath}")
    print(f"Word count: {word_count:,}")
    print(f"IBDP EE limit: 4,000 words")
    
    if word_count > 4000:
        excess = word_count - 4000
        print(f"⚠️  OVER LIMIT by {excess:,} words ({excess/4000*100:.1f}%)")
    elif word_count > 3800:
        remaining = 4000 - word_count
        print(f"⚠️  Near limit - {remaining:,} words remaining")
    else:
        remaining = 4000 - word_count
        print(f"✅ Within limit - {remaining:,} words remaining")
    
    print(f"Usage: {word_count/4000*100:.1f}% of limit")
    
    if args.show_text:
        print("\n" + "="*50)
        print("CLEANED TEXT (counted content):")
        print("="*50)
        print(cleaned_text)
    
    if args.debug:
        print(f"\nDEBUG: Cleaned text length: {len(cleaned_text)} characters")

if __name__ == "__main__":
    main()