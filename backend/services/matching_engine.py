"""Production-Grade Candidate-to-JD Matching and Explainable Scoring Engine.

Scoring & Ranking Architecture:
- Skill Normalization & Taxonomy: Maps canonical technical skills and aliases while strictly
  preventing false-positive substring matches (e.g. Java vs JavaScript, Go vs Django, C vs CSS).
- Hard Mandatory Requirements vs Required Skills: Hard mandatory requirements disqualify candidates
  (is_eligible=False, total=0.0), whereas normal required skills apply configurable proportional scoring.
- Semantic Alignment Signal: Dense vector embeddings (all-MiniLM-L6-v2 via ChromaDB) provide a calibrated
  top-K ranking signal rather than a literal match probability.
- Configurable Weights & Multi-Factor Evaluators: Experience brackets, notice period caps, and
  location/remote modes are evaluated using configurable mathematical curves.
- Explainability & Auditing: Every evaluated profile produces a granular breakdown dictionary, audit metadata,
  and a narrative human-readable explanation.
"""

from __future__ import annotations

import os
import re
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable, Any, Optional

from dotenv import load_dotenv

load_dotenv()

ENGINE_VERSION = "2.1.0"
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"


# =============================================================================
# Configuration Dataclass
# =============================================================================

@dataclass
class MatchingConfig:
    """Configurable scoring parameters, weights, and thresholds."""
    w_skills: float = 50.0
    w_experience: float = 50.0
    w_notice: float = 0.0
    w_location: float = 0.0
    
    # Semantic similarity contribution within skills component (0.0 to 1.0)
    # Calibrated ranking alignment signal
    semantic_weight_in_skills: float = 0.25
    
    # Bonus for matching nice-to-have / optional skills (scaled max 15%)
    nice_to_have_bonus_weight: float = 0.15
    
    # Normal required skills shortfall threshold: if candidate matches less than this fraction
    # of required skills (e.g. 0 skills), apply a measured shortfall penalty.
    mandatory_skills_min_ratio: float = 0.20
    mandatory_shortfall_penalty: float = 0.15  # calibrated penalty deduction ratio
    
    # Experience parameters
    over_experience_grace_years: float = 2.0  # extra years allowed beyond max experience without penalty
    
    # Engine metadata
    engine_version: str = ENGINE_VERSION
    embedding_model: str = EMBEDDING_MODEL_NAME

    def normalized_weights(self) -> tuple[float, float, float, float]:
        """Return normalized weights summing to 100."""
        total = self.w_skills + self.w_experience + self.w_notice + self.w_location
        if total <= 0:
            return 50.0, 50.0, 0.0, 0.0
        return (
            (self.w_skills / total) * 100.0,
            (self.w_experience / total) * 100.0,
            (self.w_notice / total) * 100.0,
            (self.w_location / total) * 100.0,
        )


# =============================================================================
# Score Output Dataclass
# =============================================================================

@dataclass(frozen=True)
class Score:
    """Detailed score result with factor breakdown, narrative explanation, and audit metadata."""
    total: float
    skills: float
    experience: float
    notice_period: float
    location: float
    semantic_relevance: float
    is_eligible: bool = True
    explanation: str = ""
    breakdown: dict[str, Any] = field(default_factory=dict)
    audit: dict[str, Any] = field(default_factory=dict)


# =============================================================================
# Text Normalization & Skill Taxonomy
# =============================================================================

def _normalise_text(value: str | None) -> str:
    """Clean and collapse whitespace in string."""
    if not value:
        return ""
    return re.sub(r"\s+", " ", str(value).strip().lower())


def _clean_token(s: str) -> str:
    """Strip non-alphanumeric characters while preserving meaningful technical symbols."""
    return re.sub(r"[^a-z0-9+#.]", "", s.lower().strip())


class SkillTaxonomy:
    """Canonical mapping and normalization for technical skills to prevent false matches."""

    # Canonical skill aliases map: alias -> canonical key
    CANONICAL_MAP: dict[str, str] = {
        # JavaScript / TypeScript ecosystem
        "js": "javascript",
        "javascript": "javascript",
        "ecmascript": "javascript",
        "ts": "typescript",
        "typescript": "typescript",
        "node": "nodejs",
        "node.js": "nodejs",
        "nodejs": "nodejs",
        "node js": "nodejs",
        "react": "react",
        "react.js": "react",
        "reactjs": "react",
        "react js": "react",
        "react native": "react-native",
        "react-native": "react-native",
        "vue": "vue",
        "vue.js": "vue",
        "vuejs": "vue",
        "angular": "angular",
        "angular.js": "angular",
        "angularjs": "angular",
        "next.js": "nextjs",
        "nextjs": "nextjs",
        "next js": "nextjs",
        
        # Python ecosystem
        "python": "python",
        "py": "python",
        "python3": "python",
        "fastapi": "fastapi",
        "fast api": "fastapi",
        "django": "django",
        "flask": "flask",
        
        # Java & JVM (strictly distinct from JavaScript!)
        "java": "java",
        "core java": "java",
        "java 8": "java",
        "java 11": "java",
        "java 17": "java",
        "spring": "spring",
        "spring boot": "springboot",
        "springboot": "springboot",
        "kotlin": "kotlin",
        "scala": "scala",
        
        # C / C++ / C# (strictly distinct from CSS!)
        "c": "c",
        "c language": "c",
        "c++": "cpp",
        "cpp": "cpp",
        "c#": "csharp",
        "csharp": "csharp",
        ".net": "dotnet",
        "dotnet": "dotnet",
        ".net core": "dotnet-core",
        
        # Go / Rust / PHP / Ruby
        "go": "golang",
        "golang": "golang",
        "rust": "rust",
        "php": "php",
        "ruby": "ruby",
        "ruby on rails": "rails",
        "rails": "rails",
        
        # Web / Styling
        "html": "html",
        "html5": "html",
        "css": "css",
        "css3": "css",
        "sass": "sass",
        "scss": "sass",
        "tailwind": "tailwind",
        "tailwindcss": "tailwind",
        
        # Databases & Storage
        "sql": "sql",
        "rdbms": "sql",
        "relational database": "sql",
        "postgres": "postgresql",
        "postgresql": "postgresql",
        "psql": "postgresql",
        "mysql": "mysql",
        "sqlite": "sqlite",
        "mssql": "mssql",
        "sql server": "mssql",
        "oracle": "oracle-db",
        "oracle db": "oracle-db",
        "mongodb": "mongodb",
        "mongo": "mongodb",
        "redis": "redis",
        "elasticsearch": "elasticsearch",
        "dynamodb": "dynamodb",
        "cassandra": "cassandra",
        
        # Cloud & DevOps
        "aws": "aws",
        "amazon web services": "aws",
        "gcp": "gcp",
        "google cloud": "gcp",
        "google cloud platform": "gcp",
        "azure": "azure",
        "microsoft azure": "azure",
        "docker": "docker",
        "kubernetes": "kubernetes",
        "k8s": "kubernetes",
        "terraform": "terraform",
        "ansible": "ansible",
        "jenkins": "jenkins",
        "github actions": "github-actions",
        "ci/cd": "cicd",
        "cicd": "cicd",
        
        # AI / ML / Data
        "machine learning": "ml",
        "ml": "ml",
        "artificial intelligence": "ai",
        "ai": "ai",
        "deep learning": "deep-learning",
        "nlp": "nlp",
        "natural language processing": "nlp",
        "pytorch": "pytorch",
        "tensorflow": "tensorflow",
        "keras": "keras",
        "pandas": "pandas",
        "numpy": "numpy",
        "scikit-learn": "scikit-learn",
        "sklearn": "scikit-learn",
    }

    # Strict distinct skills that must NEVER match via prefix/substring
    ISOLATED_SKILLS: set[str] = {
        "java", "javascript", "c", "cpp", "csharp", "css", "go", "golang", "r", "rust",
        "sql", "nosql", "html", "php", "aws", "gcp"
    }

    @classmethod
    def canonicalize(cls, skill: str) -> str:
        """Convert a skill string into its canonical taxonomy key."""
        norm = _normalise_text(skill)
        if not norm:
            return ""
        if norm in cls.CANONICAL_MAP:
            return cls.CANONICAL_MAP[norm]
        
        cleaned = _clean_token(norm)
        if cleaned in cls.CANONICAL_MAP:
            return cls.CANONICAL_MAP[cleaned]
            
        return cleaned or norm

    @classmethod
    def matches(cls, req_skill: str, candidate_skills: Iterable[str]) -> bool:
        """
        Check if a required skill is present in candidate skills without false positives.
        Guarantees that 'Java' does not match 'JavaScript', 'Go' does not match 'Django', etc.
        """
        req_norm = _normalise_text(req_skill)
        if not req_norm:
            return False
            
        req_canonical = cls.canonicalize(req_norm)
        
        for cand_skill in candidate_skills:
            cand_norm = _normalise_text(cand_skill)
            if not cand_norm:
                continue
                
            cand_canonical = cls.canonicalize(cand_norm)
            
            # 1. Exact canonical match
            if req_canonical == cand_canonical:
                return True
                
            # 2. Direct normalized exact match
            if req_norm == cand_norm:
                return True
                
            # 3. If either is an isolated skill, do NOT allow substring matching!
            if req_canonical in cls.ISOLATED_SKILLS or cand_canonical in cls.ISOLATED_SKILLS:
                # Hierarchical allowed equivalence: e.g. postgresql implies sql, mysql implies sql
                if req_canonical == "sql" and cand_canonical in {"postgresql", "mysql", "sqlite", "mssql", "oracle-db"}:
                    return True
                continue
                
            # 4. Multi-word phrase exact match or word-boundary containment (e.g. "amazon web services (aws)" vs "aws")
            if len(req_norm) >= 4 and len(cand_norm) >= 4:
                pattern = r"\b" + re.escape(req_norm) + r"\b"
                if re.search(pattern, cand_norm):
                    return True
                pattern_cand = r"\b" + re.escape(cand_norm) + r"\b"
                if re.search(pattern_cand, req_norm):
                    return True

        return False


# =============================================================================
# Location & Work Mode Matching
# =============================================================================

class LocationMatcher:
    """Evaluates location proximity, city aliases, metro clusters, and remote/hybrid modes."""

    CITY_ALIASES: dict[str, set[str]] = {
        "bengaluru": {"bengaluru", "bangalore", "blr", "karnataka"},
        "bangalore": {"bengaluru", "bangalore", "blr", "karnataka"},
        "mumbai": {"mumbai", "bombay", "navi mumbai", "thane", "maharashtra"},
        "bombay": {"mumbai", "bombay", "navi mumbai", "thane", "maharashtra"},
        "chennai": {"chennai", "madras", "tamil nadu", "tn"},
        "madras": {"chennai", "madras", "tamil nadu", "tn"},
        "delhi": {"delhi", "new delhi", "ncr", "noida", "gurgaon", "gurugram", "faridabad", "ghaziabad"},
        "new delhi": {"delhi", "new delhi", "ncr", "noida", "gurgaon", "gurugram"},
        "ncr": {"delhi", "new delhi", "ncr", "noida", "gurgaon", "gurugram"},
        "gurgaon": {"delhi", "new delhi", "ncr", "noida", "gurgaon", "gurugram", "haryana"},
        "gurugram": {"delhi", "new delhi", "ncr", "noida", "gurgaon", "gurugram", "haryana"},
        "noida": {"delhi", "new delhi", "ncr", "noida", "gurgaon", "gurugram", "uttar pradesh", "up"},
        "hyderabad": {"hyderabad", "secunderabad", "hyd", "telangana"},
        "kolkata": {"kolkata", "calcutta", "west bengal"},
        "pune": {"pune", "poona", "maharashtra"},
        "ahmedabad": {"ahmedabad", "gandhinagar", "gujarat"},
    }

    REMOTE_KEYWORDS: set[str] = {
        "remote", "wfh", "work from home", "anywhere", "pan india", "pan-india", "any location", "open"
    }

    @classmethod
    def evaluate(cls, candidate_location: str | None, jd_location: str | None) -> float:
        """Compute location compatibility ratio (0.0 to 1.0)."""
        if not jd_location or not jd_location.strip():
            return 1.0  # No location requirement specified
        
        jd_norm = _normalise_text(jd_location)

        # 1. Check if JD supports Remote / Anywhere / WFH
        if any(k in jd_norm for k in cls.REMOTE_KEYWORDS):
            return 1.0

        if not candidate_location or not candidate_location.strip():
            return 0.40  # Location unspecified for candidate

        cand_norm = _normalise_text(candidate_location)
            
        # 2. Check if candidate explicitly lists Remote
        if any(k in cand_norm for k in cls.REMOTE_KEYWORDS):
            return 0.85  # Candidate prefers remote; slight partial score if JD is onsite

        # 3. Direct containment match
        if cand_norm in jd_norm or jd_norm in cand_norm:
            return 1.0

        # 4. Token & Alias matching
        delimiters = r"[,/|;\-\n\t\s]|\band\b|\bor\b"
        cand_tokens = {t.strip() for t in re.split(delimiters, cand_norm) if len(t.strip()) > 1}
        jd_tokens = {t.strip() for t in re.split(delimiters, jd_norm) if len(t.strip()) > 1}

        ignore_words = {"india", "location", "city", "state", "office", "onsite", "on-site", "hybrid", "in"}
        cand_clean = {t for t in cand_tokens if t not in ignore_words}
        jd_clean = {t for t in jd_tokens if t not in ignore_words}

        for jt in jd_clean:
            for ct in cand_clean:
                if jt == ct:
                    return 1.0
                jt_aliases = cls.CITY_ALIASES.get(jt, {jt})
                ct_aliases = cls.CITY_ALIASES.get(ct, {ct})
                if jt_aliases & ct_aliases:
                    return 1.0

        # Partial credit if within same state / country or hybrid consideration
        if "hybrid" in jd_norm or "hybrid" in cand_norm:
            return 0.30

        return 0.0


# =============================================================================
# Experience & Notice Period Evaluators
# =============================================================================

class ExperienceEvaluator:
    """Evaluates candidate years of experience against JD min/max ranges with edge case handling."""

    @classmethod
    def evaluate(
        cls,
        candidate_years: float | int | str | None,
        minimum: float | int | str | None,
        maximum: float | int | str | None,
        grace_years: float = 2.0
    ) -> tuple[float, str]:
        """
        Returns (score_ratio, note).
        score_ratio: 0.0 to 1.0
        """
        if minimum is None:
            return 1.0, "No minimum experience requirement"
            
        try:
            min_yrs = float(minimum)
        except (ValueError, TypeError):
            return 1.0, "Invalid minimum experience specified"

        if candidate_years is None:
            return 0.25, "Experience not stated"

        try:
            cand_yrs = float(candidate_years)
        except (ValueError, TypeError):
            return 0.25, "Could not parse candidate experience"

        max_yrs = None
        if maximum is not None:
            try:
                max_yrs = float(maximum)
            except (ValueError, TypeError):
                max_yrs = None

        # Case 1: Within required min-max bracket
        if cand_yrs >= min_yrs:
            if max_yrs is None or cand_yrs <= (max_yrs + grace_years):
                return 1.0, f"Optimal experience ({cand_yrs:.1f} yrs vs {min_yrs:.1f}-{max_yrs if max_yrs is not None else '∞'} yrs required)"
            else:
                # Over-experienced beyond grace threshold: gentle decay down to 0.70
                over_gap = cand_yrs - (max_yrs + grace_years)
                decay = max(0.70, 1.0 - (over_gap * 0.05))
                return round(decay, 2), f"Over-experienced ({cand_yrs:.1f} yrs, max preferred {max_yrs:.1f} yrs)"

        # Case 2: Under-experienced below minimum
        if min_yrs > 0:
            ratio = max(0.0, min(1.0, cand_yrs / min_yrs))
            return round(ratio, 2), f"Under-experienced ({cand_yrs:.1f} yrs vs {min_yrs:.1f} yrs min required)"

        return 1.0, "Experience criteria satisfied"


class NoticePeriodEvaluator:
    """Evaluates candidate notice period against JD requirements."""

    @classmethod
    def evaluate(
        cls,
        candidate_notice: int | float | None,
        required_notice: int | float | None
    ) -> tuple[float, str]:
        """
        Returns (score_ratio, note).
        score_ratio: 0.0 to 1.0
        """
        if required_notice is None:
            return 1.0, "No notice period cap specified"

        if candidate_notice is None:
            return 0.50, "Notice period not specified"

        try:
            cand_days = int(candidate_notice)
            req_days = int(required_notice)
        except (ValueError, TypeError):
            return 0.50, "Unparseable notice period"

        # Immediate joiners (0-day notice) or within required cap
        if cand_days <= req_days:
            if cand_days == 0:
                return 1.0, "Immediate joiner (0 days notice)"
            return 1.0, f"Within notice cap ({cand_days} days <= {req_days} days)"

        # Exceeds cap
        if req_days <= 0:
            # JD wants immediate joiners (0 days); decay gracefully over 60 days
            ratio = max(0.0, 1.0 - (cand_days / 60.0))
            return round(ratio, 2), f"Exceeds immediate requirement ({cand_days} days notice)"

        # Linear ratio decay
        ratio = max(0.0, float(req_days) / float(max(1, cand_days)))
        return round(ratio, 2), f"Exceeds notice cap ({cand_days} days vs {req_days} days max)"


# =============================================================================
# Semantic Retrieval & Vector Index
# =============================================================================

def _candidate_document(candidate) -> str:
    """Construct search document representation for a candidate."""
    return "\n".join(filter(None, [
        getattr(candidate, "full_name", ""),
        "Skills: " + ", ".join(getattr(candidate, "skills", None) or []),
        candidate.parsed_json.get("parsed_summary", "") if getattr(candidate, "parsed_json", None) else "",
        getattr(candidate, "resume_text", "") or "",
    ]))[:14000]


def _jd_document(jd) -> str:
    """Construct search document representation for a Job Description."""
    return "\n".join(filter(None, [
        getattr(jd, "role_title", ""),
        "Required skills: " + ", ".join(getattr(jd, "required_skills", None) or []),
        "Nice-to-have skills: " + ", ".join(getattr(jd, "nice_to_have_skills", None) or []),
        getattr(jd, "raw_text", "") or "",
    ]))[:14000]


def _calibrate_semantic_relevance(distance: float) -> float:
    """
    Calibrate ChromaDB cosine distance (range [0, 2]) to a normalized 0-1 ranking alignment signal.
    Note: Dense vector similarity serves as a contextual ranking feature, not a literal probability.
    """
    raw_similarity = 1.0 - distance
    clamped = max(0.0, min(1.0, raw_similarity))
    return round(clamped, 3)


class SemanticIndex:
    """ChromaDB wrapper for semantic embedding indexing and candidate retrieval."""

    def __init__(self):
        try:
            import chromadb
            from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
        except ImportError as exc:
            raise RuntimeError(
                "Semantic matching requires chromadb and sentence-transformers. "
                "Run: pip install -r requirements.txt"
            ) from exc

        persist_dir = os.getenv("CHROMA_PERSIST_DIRECTORY", "chroma_data")
        embedding = SentenceTransformerEmbeddingFunction(
            model_name=EMBEDDING_MODEL_NAME
        )
        self.collection = chromadb.PersistentClient(path=persist_dir).get_or_create_collection(
            name="candidate_profiles",
            embedding_function=embedding,
            metadata={"hnsw:space": "cosine"},
        )

    def index_candidates(self, candidates: Iterable) -> None:
        """Upsert candidates into the vector index."""
        candidates = list(candidates)
        if not candidates:
            return
        self.collection.upsert(
            ids=[str(c.candidate_id) for c in candidates],
            documents=[_candidate_document(c) for c in candidates],
            metadatas=[{"candidate_code": c.candidate_code} for c in candidates],
        )

    def relevance_for(self, jd, candidates: Iterable) -> dict[str, float]:
        """Compute calibrated semantic relevance for target candidates."""
        candidates = list(candidates)
        if not candidates:
            return {}
            
        candidate_ids = [str(candidate.candidate_id) for candidate in candidates]
        try:
            result = self.collection.query(
                query_texts=[_jd_document(jd)],
                n_results=min(len(candidate_ids), 200),
                where={"candidate_code": {"$in": [candidate.candidate_code for candidate in candidates]}},
            )
            if not result or not result.get("ids") or not result["ids"][0]:
                return {c_id: 0.50 for c_id in candidate_ids}

            return {
                candidate_id: _calibrate_semantic_relevance(distance)
                for candidate_id, distance in zip(result["ids"][0], result["distances"][0])
                if candidate_id in candidate_ids
            }
        except Exception:
            # Fallback if query returns no embeddings yet
            return {c_id: 0.50 for c_id in candidate_ids}


# =============================================================================
# Primary Scoring Function
# =============================================================================

def score_candidate(
    candidate: Any,
    jd: Any,
    semantic_relevance: float = 0.50,
    w_skills: float | None = None,
    w_experience: float | None = None,
    w_notice: float | None = None,
    w_location: float | None = None,
    config: MatchingConfig | None = None,
    mandatory_skills: list[str] | None = None,
) -> Score:
    """
    Compute a deterministic, explainable, and production-grade 0-100 match score.

    Parameters:
    - candidate: Candidate object or mock
    - jd: JobDescription object or mock
    - semantic_relevance: Calibrated vector alignment score (0.0 to 1.0)
    - w_skills, w_experience, w_notice, w_location: Explicit weights (override config)
    - config: Optional MatchingConfig instance
    - mandatory_skills: Optional list of hard mandatory skills that disqualify candidate if missing
    """
    if config is None:
        config = MatchingConfig(
            w_skills=w_skills if w_skills is not None else 50.0,
            w_experience=w_experience if w_experience is not None else 50.0,
            w_notice=w_notice if w_notice is not None else 0.0,
            w_location=w_location if w_location is not None else 0.0,
        )
    elif any(w is not None for w in (w_skills, w_experience, w_notice, w_location)):
        config = MatchingConfig(
            w_skills=w_skills if w_skills is not None else config.w_skills,
            w_experience=w_experience if w_experience is not None else config.w_experience,
            w_notice=w_notice if w_notice is not None else config.w_notice,
            w_location=w_location if w_location is not None else config.w_location,
            semantic_weight_in_skills=config.semantic_weight_in_skills,
            nice_to_have_bonus_weight=config.nice_to_have_bonus_weight,
            mandatory_skills_min_ratio=config.mandatory_skills_min_ratio,
            mandatory_shortfall_penalty=config.mandatory_shortfall_penalty,
            over_experience_grace_years=config.over_experience_grace_years,
        )

    norm_w_skills, norm_w_exp, norm_w_notice, norm_w_loc = config.normalized_weights()

    candidate_skills = [s.strip() for s in (getattr(candidate, "skills", None) or []) if s and s.strip()]

    # 1. Hard Mandatory Requirements Check (Ineligibility Filter)
    # Extract mandatory skills from explicit param, jd.mandatory_skills, or prefixed with '*' in required_skills
    raw_required_skills = [s.strip() for s in (getattr(jd, "required_skills", None) or []) if s and s.strip()]
    
    explicit_mandatory = set(mandatory_skills or getattr(jd, "mandatory_skills", None) or [])
    clean_required = []
    for s in raw_required_skills:
        if s.startswith("*") or s.lower().startswith("[mandatory]"):
            clean_s = re.sub(r"^\*|\[mandatory\]\s*", "", s, flags=re.IGNORECASE).strip()
            explicit_mandatory.add(clean_s)
            clean_required.append(clean_s)
        else:
            clean_required.append(s)

    # Check if candidate is missing any hard mandatory skill
    missing_mandatory = [
        m for m in explicit_mandatory if not SkillTaxonomy.matches(m, candidate_skills)
    ]

    if missing_mandatory:
        # Candidate is hard-disqualified due to missing mandatory requirement
        explanation = (
            f"❌ Ineligible: Missing hard mandatory skill(s): {', '.join(missing_mandatory)}. "
            f"Candidate profile did not satisfy non-negotiable JD prerequisites."
        )
        breakdown = {
            "is_eligible": False,
            "missing_mandatory_skills": missing_mandatory,
            "matched_required_skills": [req for req in clean_required if SkillTaxonomy.matches(req, candidate_skills)],
            "missing_required_skills": [req for req in clean_required if not SkillTaxonomy.matches(req, candidate_skills)],
            "mandatory_penalty_applied": 0.0,
            "normalized_weights": {
                "w_skills": norm_w_skills,
                "w_experience": norm_w_exp,
                "w_notice": norm_w_notice,
                "w_location": norm_w_loc,
            },
        }
        audit = {
            "engine_version": config.engine_version,
            "embedding_model": config.embedding_model,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
        }
        return Score(
            total=0.0,
            skills=0.0,
            experience=0.0,
            notice_period=0.0,
            location=0.0,
            semantic_relevance=semantic_relevance,
            is_eligible=False,
            explanation=explanation,
            breakdown=breakdown,
            audit=audit,
        )

    # 2. Core Required Skills Evaluation
    matched_required = [
        req for req in clean_required if SkillTaxonomy.matches(req, candidate_skills)
    ]
    missing_required = [
        req for req in clean_required if req not in matched_required
    ]

    req_ratio = len(matched_required) / len(clean_required) if clean_required else 1.0

    # 3. Nice-to-Have Skills Bonus Evaluation
    # Deduplicate against required skills so no skill is counted as both required and bonus
    raw_nice_to_have = [s.strip() for s in (getattr(jd, "nice_to_have_skills", None) or []) if s and s.strip()]
    clean_nice_to_have = [
        nice for nice in raw_nice_to_have
        if not any(SkillTaxonomy.canonicalize(nice) == SkillTaxonomy.canonicalize(req) for req in clean_required)
    ]
    matched_nice = [
        nice for nice in clean_nice_to_have if SkillTaxonomy.matches(nice, candidate_skills)
    ]
    nice_ratio = len(matched_nice) / len(clean_nice_to_have) if clean_nice_to_have else 0.0

    # Combined skill ratio incorporating keyword match, nice-to-have bonus, and semantic alignment
    kw_component = req_ratio + (nice_ratio * config.nice_to_have_bonus_weight)
    kw_component = min(1.0, kw_component)

    sem_weight = config.semantic_weight_in_skills
    skills_ratio = ((1.0 - sem_weight) * kw_component) + (sem_weight * semantic_relevance)
    skills_ratio = max(0.0, min(1.0, skills_ratio))

    # 4. Experience Evaluation
    exp_ratio, exp_note = ExperienceEvaluator.evaluate(
        getattr(candidate, "total_experience", None),
        getattr(jd, "experience_min", None),
        getattr(jd, "experience_max", None),
        grace_years=config.over_experience_grace_years,
    )

    # 5. Notice Period Evaluation
    notice_ratio, notice_note = NoticePeriodEvaluator.evaluate(
        getattr(candidate, "notice_period_days", None),
        getattr(jd, "notice_period_days", None),
    )

    # 6. Location Evaluation
    loc_ratio = LocationMatcher.evaluate(
        getattr(candidate, "current_location", None),
        getattr(jd, "location", None),
    )

    # Factor points
    skills_score = round(skills_ratio * norm_w_skills, 2)
    experience_score = round(exp_ratio * norm_w_exp, 2)
    notice_score = round(notice_ratio * norm_w_notice, 2)
    location_score = round(loc_ratio * norm_w_loc, 2)

    raw_total = skills_score + experience_score + notice_score + location_score

    # 7. Normal Required Skills Shortfall Penalty
    penalty_applied = 0.0
    penalty_reason = None
    if clean_required and len(clean_required) >= 2:
        if req_ratio < config.mandatory_skills_min_ratio:
            penalty_applied = round(raw_total * config.mandatory_shortfall_penalty, 2)
            penalty_reason = (
                f"Candidate matched only {len(matched_required)}/{len(clean_required)} required skills "
                f"({req_ratio:.0%} < {config.mandatory_skills_min_ratio:.0%} threshold)"
            )

    final_total = max(0.0, min(100.0, round(raw_total - penalty_applied, 2)))

    # 8. Narrative Explanation
    explanation_parts = [
        f"Skills: {len(matched_required)}/{len(clean_required)} required skills matched "
        f"({', '.join(matched_required) if matched_required else 'none'}); "
        f"semantic alignment {semantic_relevance:.0%}."
    ]
    if matched_nice:
        explanation_parts.append(f"Bonus skills: {', '.join(matched_nice)}.")
    if missing_required:
        explanation_parts.append(f"Missing core: {', '.join(missing_required[:5])}.")

    explanation_parts.append(f"Experience: {exp_note}.")
    explanation_parts.append(f"Notice: {notice_note}.")
    
    cand_loc = getattr(candidate, "current_location", None) or "Unstated"
    jd_loc = getattr(jd, "location", None) or "Anywhere"
    explanation_parts.append(f"Location: {cand_loc} vs {jd_loc} ({int(loc_ratio * 100)}% compatible).")

    if penalty_applied > 0:
        explanation_parts.append(f"⚠️ Penalty: -{penalty_applied} pts ({penalty_reason}).")

    explanation = " ".join(explanation_parts)

    breakdown = {
        "is_eligible": True,
        "matched_required_skills": matched_required,
        "missing_required_skills": missing_required,
        "matched_nice_to_have_skills": matched_nice,
        "required_skills_ratio": round(req_ratio, 2),
        "nice_to_have_ratio": round(nice_ratio, 2),
        "semantic_relevance": round(semantic_relevance, 3),
        "experience_ratio": round(exp_ratio, 2),
        "experience_evaluation": exp_note,
        "notice_period_ratio": round(notice_ratio, 2),
        "notice_period_evaluation": notice_note,
        "location_compatibility_ratio": round(loc_ratio, 2),
        "mandatory_penalty_applied": penalty_applied,
        "normalized_weights": {
            "w_skills": norm_w_skills,
            "w_experience": norm_w_exp,
            "w_notice": norm_w_notice,
            "w_location": norm_w_loc,
        },
    }

    audit = {
        "engine_version": config.engine_version,
        "embedding_model": config.embedding_model,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
    }

    return Score(
        total=final_total,
        skills=skills_score,
        experience=experience_score,
        notice_period=notice_score,
        location=location_score,
        semantic_relevance=semantic_relevance,
        is_eligible=True,
        explanation=explanation,
        breakdown=breakdown,
        audit=audit,
    )
