import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from typing import List, Dict, Any, Optional

class LawRepository:
    def __init__(self, db_path: str = "backend/data/ysz.db"):
        # Ensure absolute path
        if not os.path.isabs(db_path):
             # Assuming running from project root
             db_path = os.path.abspath(db_path)
             
        self.engine = create_engine(f"sqlite:///{db_path}")
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self._ensure_table_exists()

    def _ensure_table_exists(self):
        # Full Schema Definition matching LawDetails model + Missing columns
        query = text("""
            CREATE TABLE IF NOT EXISTS law_details (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                law_name_kr TEXT,
                promulgation_number TEXT,
                enforcement_date TEXT,
                reference TEXT,
                status TEXT,
                file_path TEXT,
                promulgation_date TEXT,
                amendment_type TEXT,
                article_num TEXT,
                article_branch_num INTEGER,
                article_check TEXT,
                article_title TEXT,
                article_enforce_date TEXT,
                article_content TEXT,
                paragraph_num INTEGER,
                paragraph_content TEXT,
                subparagraph_num INTEGER,
                subparagraph_content TEXT,
                item_num INTEGER,
                item_content TEXT,
                image_url TEXT,
                addendum_date TEXT,
                addendum_content TEXT,
                law_abbrev TEXT
            )
        """)
        with self.engine.connect() as conn:
            conn.execute(query)
            conn.commit()

    def get_session(self) -> Session:
        return self.SessionLocal()

    def search_articles(self, keyword: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search for articles containing the keyword in title or content.
        """
        query = text("""
            SELECT law_name_kr, article_num, article_title, article_content
            FROM law_details 
            WHERE article_content LIKE :keyword OR article_title LIKE :keyword
            LIMIT :limit
        """)
        
        with self.get_session() as session:
            result = session.execute(query, {"keyword": f"%{keyword}%", "limit": limit})
            return [row._mapping for row in result]

    def get_law_content(self, law_name: str) -> List[Dict[str, Any]]:
         """
         Get all content for a specific law.
         """
         query = text("""
            SELECT *
            FROM law_details
            WHERE law_name_kr = :law_name
            ORDER BY 
                CAST(article_num AS INTEGER) ASC, 
                article_branch_num ASC, 
                paragraph_num ASC, 
                subparagraph_num ASC, 
                item_num ASC
         """)
         with self.get_session() as session:
            result = session.execute(query, {"law_name": law_name})
            return [row._mapping for row in result]

    def get_all_laws(self) -> List[Dict[str, Any]]:
        """
        Get unique list of laws with metadata.
        """
        # SQLite doesn't have a sophisticated distinct on multiple columns if we want just one row per law.
        # But here we assume law_name_kr is unique enough or we group by it.
        # Let's select distinct law identifiers.
        # Group by law name to ensure unique list, taking the latest enforcement date
        # Order by hierarchy: Law (no modifier) -> Decree (시행령) -> Rule (시행규칙)
        query = text("""
            SELECT 
                law_name_kr, 
                MAX(enforcement_date) as enforcement_date, 
                MAX(law_abbrev) as law_abbrev, 
                MAX(status) as status,
                MAX(reference) as reference,
                MAX(promulgation_date) as promulgation_at,
                MAX(promulgation_number) as promulgation_number,
                MAX(amendment_type) as amendment_type,
                MAX(file_path) as file_path
            FROM law_details
            GROUP BY law_name_kr
            ORDER BY 
                REPLACE(REPLACE(law_name_kr, ' 시행규칙', ''), ' 시행령', ''),
                CASE 
                    WHEN law_name_kr NOT LIKE '%시행%' THEN 1
                    WHEN law_name_kr LIKE '%시행령%' THEN 2
                    WHEN law_name_kr LIKE '%시행규칙%' THEN 3
                    ELSE 4
                END,
                CAST(enforcement_date AS INTEGER) DESC
        """)
        with self.get_session() as session:
            result = session.execute(query)
            return [row._mapping for row in result]

    def update_law_status(self, law_name: str, new_status: str) -> None:
        """
        Update the status of a law (all rows for that law).
        """
        query = text("""
            UPDATE law_details
            SET status = :status
            WHERE law_name_kr = :law_name
        """)
        with self.get_session() as session:
            session.execute(query, {"status": new_status, "law_name": law_name})
            session.commit()

    def delete_law(self, law_name: str) -> List[str]:
        """
        Delete a law (all rows) and return associated file paths if any.
        """
        # First get file paths to delete
        query_select = text("SELECT file_path FROM law_details WHERE law_name_kr = :law_name AND file_path IS NOT NULL")
        query_delete = text("DELETE FROM law_details WHERE law_name_kr = :law_name")
        
        file_paths = []
        with self.get_session() as session:
            rows = session.execute(query_select, {"law_name": law_name}).fetchall()
            file_paths = [row[0] for row in rows if row[0]]
            
            session.execute(query_delete, {"law_name": law_name})
            session.commit()
            
        return file_paths

    def save_reference_doc(self, data: Dict[str, Any]) -> None:
        """
        Insert a single row for a reference document.
        """
        query = text("""
            INSERT INTO law_details (
                law_name_kr, promulgation_number, enforcement_date, reference, 
                status, file_path, promulgation_date, amendment_type
            ) VALUES (
                :law_name_kr, :promulgation_number, :enforcement_date, :reference,
                :status, :file_path, :promulgation_date, :amendment_type
            )
        """)
        with self.get_session() as session:
            session.execute(query, data)
            session.commit()

# Singleton instance
_repo = None

def get_law_repository() -> LawRepository:
    global _repo
    if _repo is None:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(current_dir, "..", "..", "data", "ysz.db")
        _repo = LawRepository(db_path)
    return _repo
