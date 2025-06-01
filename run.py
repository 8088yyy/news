#!/usr/bin/env python3
"""
Makkal Kural E-Paper Downloader
Downloads all pages of the daily e-paper and combines them into a single PDF
"""

import requests
import json
import logging
from datetime import datetime
from pathlib import Path
import PyPDF2
from PyPDF2 import PdfWriter, PdfReader
import sys
import time
from typing import List, Dict, Optional

# Configure logging
def setup_logging():
    """Setup logging configuration"""
    log_format = '%(asctime)s - %(levelname)s - %(message)s'
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[
            logging.FileHandler('log.txt', encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)

class MakkalKuralDownloader:
    def __init__(self):
        self.base_url = "http://epaper.makkalkural.net"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.logger = setup_logging()
        self.temp_dir = Path("temp_pdfs")
        self.temp_dir.mkdir(exist_ok=True)
        
    def get_current_date(self) -> str:
        """Get current date in dd/mm/yyyy format"""
        return datetime.now().strftime("%d/%m/%Y")
    
    def get_all_pages(self, date: str) -> List[Dict]:
        """
        Get all page information for a given date
        
        Args:
            date: Date in dd/mm/yyyy format
            
        Returns:
            List of page information dictionaries
        """
        url = f"{self.base_url}/Home/GetAllpages"
        params = {
            'editionid': 1,
            'editiondate': date
        }
        
        try:
            self.logger.info(f"Fetching page list for date: {date}")
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            pages_data = response.json()
            self.logger.info(f"Found {len(pages_data)} pages")
            return pages_data
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error fetching page list: {e}")
            return []
        except json.JSONDecodeError as e:
            self.logger.error(f"Error parsing JSON response: {e}")
            return []
    
    def get_page_download_info(self, page_id: str, date: str) -> Optional[Dict]:
        """
        Get download information for a specific page
        
        Args:
            page_id: Page ID
            date: Date in dd/mm/yyyy format
            
        Returns:
            Dictionary containing download information
        """
        url = f"{self.base_url}/Home/downloadpdfedition_page"
        params = {
            'id': page_id,
            'type': 1,
            'EditionId': 1,
            'Date': date
        }
        
        try:
            self.logger.info(f"Getting download info for page ID: {page_id}")
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            download_info = response.json()
            return download_info
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error fetching download info for page {page_id}: {e}")
            return None
        except json.JSONDecodeError as e:
            self.logger.error(f"Error parsing download info JSON for page {page_id}: {e}")
            return None
    
    def download_pdf_page(self, filename: str, page_num: int) -> Optional[Path]:
        """
        Download a single PDF page
        
        Args:
            filename: Filename from the download info
            page_num: Page number for naming
            
        Returns:
            Path to downloaded file or None if failed
        """
        url = f"{self.base_url}/Home/Download"
        params = {'Filename': filename}
        
        try:
            self.logger.info(f"Downloading page {page_num}: {filename}")
            response = self.session.get(url, params=params, timeout=60, stream=True)
            response.raise_for_status()
            
            # Save to temp directory
            file_path = self.temp_dir / f"page_{page_num:02d}.pdf"
            
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            self.logger.info(f"Successfully downloaded page {page_num}")
            return file_path
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error downloading page {page_num}: {e}")
            return None
    
    def combine_pdfs(self, pdf_files: List[Path], output_filename: str) -> bool:
        """
        Combine multiple PDF files into one
        
        Args:
            pdf_files: List of PDF file paths
            output_filename: Output filename
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.logger.info(f"Combining {len(pdf_files)} PDF files")
            pdf_writer = PdfWriter()
            
            for pdf_file in sorted(pdf_files):
                if pdf_file.exists():
                    try:
                        with open(pdf_file, 'rb') as f:
                            pdf_reader = PdfReader(f)
                            for page in pdf_reader.pages:
                                pdf_writer.add_page(page)
                        self.logger.info(f"Added {pdf_file.name} to combined PDF")
                    except Exception as e:
                        self.logger.error(f"Error processing {pdf_file}: {e}")
                        continue
            
            # Write combined PDF
            with open(output_filename, 'wb') as output_file:
                pdf_writer.write(output_file)
            
            self.logger.info(f"Successfully created combined PDF: {output_filename}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error combining PDFs: {e}")
            return False
    
    def cleanup_temp_files(self):
        """Clean up temporary files"""
        try:
            for file in self.temp_dir.glob("*.pdf"):
                file.unlink()
            self.temp_dir.rmdir()
            self.logger.info("Cleaned up temporary files")
        except Exception as e:
            self.logger.warning(f"Error cleaning up temp files: {e}")
    
    def download_daily_paper(self, date: str = None) -> bool:
        """
        Download complete daily paper
        
        Args:
            date: Date in dd/mm/yyyy format (uses current date if None)
            
        Returns:
            True if successful, False otherwise
        """
        if date is None:
            date = self.get_current_date()
        
        self.logger.info(f"Starting download for date: {date}")
        
        # Get all pages
        pages = self.get_all_pages(date)
        if not pages:
            self.logger.error("No pages found")
            return False
        
        downloaded_files = []
        
        # Process each page
        for i, page in enumerate(pages, 1):
            try:
                page_id = page.get('PageId')
                if not page_id:
                    self.logger.warning(f"No PageId found for page {i}")
                    continue
                
                # Get download info
                download_info = self.get_page_download_info(str(page_id), date)
                if not download_info:
                    self.logger.warning(f"No download info for page {i}")
                    continue
                
                filename = download_info.get('FileName')
                if not filename:
                    self.logger.warning(f"No filename found for page {i}")
                    continue
                
                # Download the PDF
                pdf_file = self.download_pdf_page(filename, i)
                if pdf_file:
                    downloaded_files.append(pdf_file)
                
                # Small delay between downloads
                time.sleep(1)
                
            except Exception as e:
                self.logger.error(f"Error processing page {i}: {e}")
                continue
        
        if not downloaded_files:
            self.logger.error("No files were downloaded successfully")
            return False
        
        # Combine all PDFs
        output_filename = f"MakkalKural_{date.replace('/', '-')}.pdf"
        success = self.combine_pdfs(downloaded_files, output_filename)
        
        # Cleanup
        self.cleanup_temp_files()
        
        if success:
            self.logger.info(f"Successfully created: {output_filename}")
            return True
        else:
            self.logger.error("Failed to create combined PDF")
            return False

def main():
    """Main function"""
    downloader = MakkalKuralDownloader()
    
    # You can specify a custom date here, or use None for current date
    custom_date = None  # Format: "dd/mm/yyyy" or None for today
    
    try:
        success = downloader.download_daily_paper(custom_date)
        if success:
            print("✅ Download completed successfully!")
        else:
            print("❌ Download failed. Check log.txt for details.")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n⏹️ Download interrupted by user")
        downloader.cleanup_temp_files()
        sys.exit(0)
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        print("❌ An unexpected error occurred. Check log.txt for details.")
        sys.exit(1)

if __name__ == "__main__":
    main()