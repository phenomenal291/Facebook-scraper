from sqlalchemy import create_engine, Column, String, DateTime, Integer, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import logging
from datetime import datetime
from sqlalchemy.dialects.mssql import NVARCHAR
import unicodedata
import pandas as pd

# Create base class for declarative models
Base = declarative_base()

def clean_text(text):
    """
    Remove or replace characters that cause Excel errors.
    Handles multiple styles of Unicode mathematical alphabetic symbols.
    """
    if not isinstance(text, str):
        return text
    
    # Dictionary of Unicode mathematical alphabetic symbols and their replacements
    replacements = {
        # Bold
        range(0x1D400, 0x1D433): lambda c: chr(ord(c) - 0x1D400 + ord('A')),  # Bold A-Z and a-z
        range(0x1D7CE, 0x1D7FF): lambda c: chr(ord(c) - 0x1D7CE + ord('0')),  # Bold numbers
        
        # Italic
        range(0x1D434, 0x1D467): lambda c: chr(ord(c) - 0x1D434 + ord('A')),  # Italic A-Z and a-z
        
        # Bold Italic
        range(0x1D468, 0x1D49B): lambda c: chr(ord(c) - 0x1D468 + ord('A')),  # Bold Italic A-Z and a-z
        
        # Script
        range(0x1D49C, 0x1D4CF): lambda c: chr(ord(c) - 0x1D49C + ord('A')),  # Script A-Z and a-z
        
        # Bold Script
        range(0x1D4D0, 0x1D503): lambda c: chr(ord(c) - 0x1D4D0 + ord('A')),  # Bold Script A-Z and a-z
        
        # Fraktur
        range(0x1D504, 0x1D537): lambda c: chr(ord(c) - 0x1D504 + ord('A')),  # Fraktur A-Z and a-z
        
        # Double-struck
        range(0x1D538, 0x1D56B): lambda c: chr(ord(c) - 0x1D538 + ord('A')),  # Double-struck A-Z and a-z
        
        # Bold Fraktur
        range(0x1D56C, 0x1D59F): lambda c: chr(ord(c) - 0x1D56C + ord('A')),  # Bold Fraktur A-Z and a-z
        
        # Sans-serif
        range(0x1D5A0, 0x1D5D3): lambda c: chr(ord(c) - 0x1D5A0 + ord('A')),  # Sans-serif A-Z and a-z
        
        # Sans-serif Bold
        range(0x1D5D4, 0x1D607): lambda c: chr(ord(c) - 0x1D5D4 + ord('A')),  # Sans-serif Bold A-Z and a-z
        range(0x1D7EC, 0x1D7F6): lambda c: chr(ord(c) - 0x1D7EC + ord('0')),  # Sans-serif Bold numbers
        
        # Sans-serif Italic
        range(0x1D608, 0x1D63B): lambda c: chr(ord(c) - 0x1D608 + ord('A')),  # Sans-serif Italic A-Z and a-z
    }
    
    
    # First normalize the text - this will separate characters from combining marks
    normalized = unicodedata.normalize('NFKD', text)
    result = ""
    for char in normalized:
        code = ord(char)
        
        # Skip control characters except tab, LF, CR
        if code < 32 and code not in (9, 10, 13):
            continue
        
        # Try replacing mathematical symbols
        replaced = False
        for char_range, replacement_func in replacements.items():
            if code in char_range:
                result += replacement_func(char)
                replaced = True
                break
        
        # Keep the character if it wasn't replaced and is in BMP
        if not replaced:
            if code < 65536:  # Basic Multilingual Plane
                result += char
    return result

class FacebookPost(Base):
    """SQLAlchemy model for Facebook posts"""
    __tablename__ = 'facebook_posts'

    id = Column(Integer, primary_key=True)
    text = Column(String(length=None).with_variant(NVARCHAR(None), 'mssql'))  # Use NVARCHAR(MAX)
    link = Column(String(500).with_variant(NVARCHAR(500), 'mssql'))
    date = Column(String(100).with_variant(NVARCHAR(100), 'mssql'))
    images = Column(JSON)
    videos = Column(JSON)
    keyword = Column(String(255).with_variant(NVARCHAR(255), 'mssql'))
    created_at = Column(DateTime, default=datetime.utcnow)

def save_to_database(data, connection_string):
    """
    Saves scraped Facebook posts to SQL Server database.
    
    Args:
        data: List of post dictionaries
        connection_string: SQL Server connection string
    """
    engine = None
    try:
        # Create database engine
        engine = create_engine(connection_string)
        
        # Create tables if they don't exist
        Base.metadata.create_all(engine)
        
        # Create session factory
        Session = sessionmaker(bind=engine)
        session = Session()

        # Clean and prepare data
        cleaned_data = []
        for post in data:
            # Clean text before storing in database
            cleaned_text = clean_text(post.get('text', ''))
            
            cleaned_post = FacebookPost(
                text=cleaned_text,
                link=post.get('link', ''),
                date=post.get('date', ''),
                images=post.get('images', []),
                videos=post.get('videos', []),
                keyword=post.get('keyword', '')
            )
            cleaned_data.append(cleaned_post)

        try:
            # Add all posts to session
            session.bulk_save_objects(cleaned_data)
            # Commit the transaction
            session.commit()
            logging.info(f"Successfully saved {len(cleaned_data)} posts to database")
            
        except Exception as e:
            session.rollback()
            logging.error(f"Failed to save posts to database: {str(e)}")
            raise
        
        finally:
            session.close()
            
    except Exception as e:
        logging.error(f"Database connection error: {str(e)}")
        raise
    
    finally:
        if engine is not None:
            engine.dispose()

# Example connection string
# CONNECTION_STRING = "mssql+pyodbc://username:password@server/database?driver=ODBC+Driver+17+for+SQL+Server"
def save_to_excel(data, filename="facebook_posts.xlsx"):
    """
    Saves scraped post data to an Excel file with plain text formatting.

    Args:
        data: List of post dictionaries
        filename: Output Excel file name
    """
    # Clean text before creating DataFrame
    cleaned_data = []
    for post in data:
        cleaned_post = {}
        for key, value in post.items():
            if key == 'text':
                # Assuming clean_text is defined in this file
                cleaned_post[key] = clean_text(value)
            else:
                cleaned_post[key] = value
        cleaned_data.append(cleaned_post)

    # Convert to a DataFrame
    df = pd.DataFrame(cleaned_data).fillna('')

    # Group by 'text'
    grouped = df.groupby('text', as_index=False).agg({
        'text': 'first',
        'link': lambda links: next((ln for ln in links if ln), ''),  # first non-empty link
        'date': 'first',  # Keep first date
        'images': 'first',  # Keep first images list
        'videos': 'first',  # Keep first videos list
        'keyword': lambda kw: ', '.join(set(kw))  # Combine keywords
    })

    grouped.sort_values(by='keyword', inplace=True)

    # Reorder columns to put text and link first
    column_order = ['text', 'link', 'date', 'images', 'videos', 'keyword']
    grouped = grouped[column_order]

    try:
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            grouped.to_excel(writer, sheet_name="Posts", index=False)
            worksheet = writer.sheets["Posts"]
            for row in worksheet.iter_rows():
                for cell in row:
                    cell.number_format = '@'
    except Exception as e:
        logging.error(f"Failed to save data to Excel: {e}")
        return

    logging.info(f"Data saved to {filename}")