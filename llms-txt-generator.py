"""
LLMs.txt Generator v1.0
Automated creation of AI-friendly documentation files
"""

import argparse
import os
import re
import requests
import time
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urlunparse
from markdownify import markdownify as md
from tqdm import tqdm
from typing import List, Dict, Set

class LLMsGenerator:
    def __init__(self, base_url: str, output_dir: str = './output', 
                 ignore_paths: List[str] = None, delay: float = 1.0):
        self.base_url = base_url.rstrip('/')
        self.output_dir = output_dir
        self.ignore_paths = set(ignore_paths or [])
        self.delay = delay
        self.visited_urls: Set[str] = set()
        self.site_data: List[Dict] = []
        self.domain = urlparse(base_url).netloc

    def _sanitize_filename(self, url: str) -> str:
        """Convert URL to filesystem-safe name without trailing underscores"""
        parsed = urlparse(url)
        path = parsed.path.strip('/')  # Remove leading/trailing slashes
        
        if not path:  # Handle root URL
            return 'index.md'
        
        # Replace special characters with hyphens
        safe_name = re.sub(r'[^a-zA-Z0-9-]', '-', path)
        
        # Remove trailing underscores/hyphens
        safe_name = safe_name.rstrip('-_')
        
        return f"{safe_name}.md"

    def _is_valid_url(self, url: str) -> bool:
        """Validate URLs for processing"""
        parsed = urlparse(url)
        return (
            parsed.netloc == self.domain and
            not any(url.startswith(p) for p in self.ignore_paths) and
            parsed.path.split('.')[-1] not in {'png', 'jpg', 'pdf', 'css', 'js'}
        )
    
    def _normalize_url(self, url: str) -> str:
        """Standardize URL format"""
        parsed = urlparse(url)
        # Remove fragments/query params and enforce trailing slash
        clean_path = parsed.path.rstrip('/') + '/'
        return urlunparse((
            parsed.scheme,
            parsed.netloc,
            clean_path,
            '', '', ''
        ))

    def _is_new_page(self, url: str) -> bool:
        """Check if URL is unique"""
        normalized = self._normalize_url(url)
        return normalized not in self.visited_urls

    def _clean_html(self, soup: BeautifulSoup) -> BeautifulSoup:
        """Remove non-content elements"""
        for element in soup(['nav', 'header', 'footer', 'script', 'style']):
            element.decompose()
        return soup

    def _fetch_page(self, url: str) -> str:
        """Fetch page content with rate limiting"""
        time.sleep(self.delay)
        try:
            response = requests.get(url, timeout=10, headers={
                'User-Agent': 'LLMs.txt Generator/1.0 (+https://github.com/llms-txt/generator)'
            })
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"\n⚠️ Error fetching {url}: {str(e)}")
            return ""

    def _convert_to_markdown(self, html: str, url: str) -> str:
        """Convert HTML to clean markdown"""
        soup = BeautifulSoup(html, 'html.parser')
        soup = self._clean_html(soup)
        
        # Create markdown header
        title = soup.title.string.strip() if soup.title else url
        header = f"# {title}\n\n"
        
        # Convert main content
        main_content = soup.find('main') or soup.body
        return header + md(str(main_content)) if main_content else ""

    def _crawl(self, url: str):
        """Recursive crawler with progress tracking"""

        normalized_url = self._normalize_url(url)
    
        if not self._is_new_page(normalized_url):
            return
    
        self.visited_urls.add(normalized_url)

        # url = normalized_url

        html = self._fetch_page(url)
        if not html:
            return

        markdown = self._convert_to_markdown(html, url)
        filename = self._sanitize_filename(url)
        
        # Save individual .html.md file
        md_dir = os.path.join(self.output_dir, 'markdown')
        os.makedirs(md_dir, exist_ok=True)
        with open(os.path.join(md_dir, filename), 'w', encoding='utf-8') as f:
            f.write(markdown)

        self.site_data.append({
            'url': url,
            'md_path': filename,  # Remove "markdown/" prefix
            'title': BeautifulSoup(html, 'html.parser').title.string.strip() if BeautifulSoup(html, 'html.parser').title else filename,
            'description': (BeautifulSoup(html, 'html.parser')
                            .find('meta', attrs={'name': 'description'})['content'] 
                            if BeautifulSoup(html, 'html.parser').find('meta', attrs={'name': 'description'}) 
                            else "")
        })

        # Find and process links
        soup = BeautifulSoup(html, 'html.parser')
        for link in tqdm(soup.find_all('a', href=True), desc=f"Processing links from {url}"):
            absolute_url = urljoin(url, link['href'])
            if self._is_valid_url(absolute_url):
                self._crawl(absolute_url)

    def generate(self):
        """Main generation workflow"""
        print(f"🚀 Starting LLMs.txt generation for {self.base_url}")
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Start crawling
        self._crawl(self.base_url)
        
        # Generate llms.txt
        core_docs = []
        optional_docs = []
        for page in self.site_data:
            if any(kw in page['url'].lower() for kw in ['doc', 'guide', 'api', 'help']):
                core_docs.append(page)
            else:
                optional_docs.append(page)

        llms_txt = [
            f"# {self.domain}",
            "> AI-friendly documentation generated by LLMs.txt Generator\n"
        ]

        if core_docs:
            llms_txt.append("## Core Documentation")
            for doc in core_docs:
                md_path = doc.get('md_path', doc['url'])  # Use correct md_path if available
                md_url = f"{self.base_url.rstrip('/')}/{md_path}"
                llms_txt.append(f"- [{doc['title']}]({md_url}): {doc['description']}")

        if optional_docs:
            llms_txt.append("\n## Optional")
            for doc in optional_docs:
                md_path = doc.get('md_path', doc['url'])  # Ensure correct path
                md_url = f"{self.base_url.rstrip('/')}/{md_path}"
                llms_txt.append(f"- [{doc['title']}]({md_url}): {doc['description']}")

        # Generate llms-full.txt
        llms_full = []
        for doc in self.site_data:
            md_path = os.path.join(self.output_dir, doc.get('md_path', doc['url']))
            if os.path.exists(md_path):  # Ensure file exists before reading
                with open(md_path, 'r', encoding='utf-8') as f:
                    llms_full.append(f"# {doc['title']}\n\n{f.read()}\n\n---\n")

        # Write output files
        with open(os.path.join(self.output_dir, 'llms.txt'), 'w', encoding='utf-8') as f:
            f.write('\n'.join(llms_txt))

        with open(os.path.join(self.output_dir, 'llms-full.txt'), 'w', encoding='utf-8') as f:
            f.write('\n'.join(llms_full))

        print(f"\n✅ Success! Generated files in {self.output_dir}/")
        print("├── llms.txt")
        print("├── llms-full.txt")
        print("└── markdown/")
        print("    ├── index.html.md")
        print("    └── ...other generated files")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Generate LLMs.txt files for a website')
    parser.add_argument('url', help='Base URL to process')
    parser.add_argument('-o', '--output', default='./output', help='Output directory')
    parser.add_argument('--ignore', nargs='+', help='Paths to ignore', default=[])
    parser.add_argument('--delay', type=float, default=1.0, 
                       help='Delay between requests (seconds)')
    
    args = parser.parse_args()
    
    generator = LLMsGenerator(
        base_url=args.url,
        output_dir=args.output,
        ignore_paths=args.ignore,
        delay=args.delay
    )
    generator.generate()