export const parseCSV = (text: string): string[][] => {
  const rows: string[][] = [];
  let currentRow: string[] = [];
  let currentCell = '';
  let insideQuotes = false;

  for (let i = 0; i < text.length; i++) {
    const char = text[i];
    
    if (char === '"') {
      if (insideQuotes && text[i+1] === '"') {
        currentCell += '"';
        i++; // skip escaped quote
      } else {
        insideQuotes = !insideQuotes;
      }
    } else if (char === ',' && !insideQuotes) {
      currentRow.push(currentCell.trim());
      currentCell = '';
    } else if ((char === '\n' || char === '\r') && !insideQuotes) {
      if (char === '\r' && text[i+1] === '\n') {
        i++; // skip \n grouping
      }
      currentRow.push(currentCell.trim());
      if (currentRow.length > 1 || currentRow[0] !== '') {
        rows.push(currentRow);
      }
      currentRow = [];
      currentCell = '';
    } else {
      currentCell += char;
    }
  }

  if (currentCell !== '' || currentRow.length > 0) {
    currentRow.push(currentCell.trim());
    if (currentRow.length > 1 || currentRow[0] !== '') {
      rows.push(currentRow);
    }
  }

  return rows;
};

const cleanTextEnums = (text: string): string => {
  if (!text) return "";
  // Remove technical prefixes from exported JSONs if standard
  return text.replace(/\b\w+\.\w+\b/g, '').trim();
};

const cleanJsonPunctuation = (text: string): string => {
  if (!text) return "";
  let clean = text.replace(/[{}\[\]"'\n]/g, ' ');
  return clean.replace(/\s+/g, ' ').trim();
};

export const parseCandidatesCSV = async (file: File): Promise<any[]> => {
  const text = await file.text();
  const rows = parseCSV(text);
  
  if (rows.length < 2) return [];

  const headers = rows[0].map(h => h.toLowerCase().trim());
  const candidates: any[] = [];

  for (let i = 1; i < rows.length; i++) {
    const row = rows[i];
    const rowData: Record<string, string> = {};
    headers.forEach((h, idx) => {
      rowData[h] = row[idx] || '';
    });

    const name = rowData['full_name'] || rowData['name'];
    if (!name || name === 'nan' || name === 'Unknown') continue;

    const email = `${name.toLowerCase().replace(/\s+/g, '.')}@candidate.com`;

    const skillsSet = new Set<string>();
    // Collect specific known fields
    const skillColumns = ['parsed_skills', 'programming_languages', 'backend_frameworks', 'frontend_technologies'];
    skillColumns.forEach(sc => {
      const val = rowData[sc];
      if (val) {
        val.split(',').forEach(s => {
          const cleaned = s.trim().toLowerCase();
          if (cleaned) skillsSet.add(cleaned);
        });
      }
    });

    // Also snag any column that has "skill" in the header
    headers.forEach(h => {
      if (h.includes('skill') && !skillColumns.includes(h)) {
        const val = rowData[h];
        if (val) {
          val.split(',').forEach(s => {
            const cleaned = s.trim().toLowerCase();
            if (cleaned) skillsSet.add(cleaned);
          });
        }
      }
    });

    const summary = cleanTextEnums(rowData['parsed_summary'] || '');
    const workExp = cleanTextEnums(cleanJsonPunctuation(rowData['parsed_work_experience'] || ''));
    
    // Concatenate all fields if no summary provided
    let resumeText = `${summary}\n\nWork Experience:\n${workExp}`.trim();
    if (!resumeText || resumeText === "Work Experience:") {
       const allFieldsArray = Object.entries(rowData).map(([k,v]) => `${k.toUpperCase()}: ${v}`);
       resumeText = allFieldsArray.join('\n');
    }

    let yoe: number | null = null;
    const yoeRaw = rowData['years_of_experience'];
    if (yoeRaw) {
      const parsed = parseFloat(yoeRaw);
      if (!isNaN(parsed) && parsed > 0) yoe = parsed;
    }

    const currentRole = rowData['current_title'] || null;

    candidates.push({
      name,
      email,
      resume_text: resumeText,
      skills: Array.from(skillsSet),
      years_of_experience: yoe,
      current_role: currentRole
    });
  }

  return candidates;
};

const DUTY_KEYWORDS = [
  "framework", "system", "pipeline", "testing", "monitoring",
  "generation", "application", "management", "strategy", "process",
  "solution", "practice", "methodology", "environment", "integration",
  "deployment", "architecture", "optimization", "analysis", "design",
  "experience", "ability", "responsible", "manage"
];

const SKILL_WHITELIST = new Set([
  "machine learning", "deep learning", "natural language processing",
  "generative ai", "prompt engineering", "api development",
  "cloud infrastructure", "distributed systems", "vector databases",
  "weights & biases", "mlflow", "scikit-learn", "tensorflow",
  "a/b testing", "ci/cd", "mlops", "nlp", "rag"
]);

function isSkill(s: string): boolean {
  const lower = s.toLowerCase().trim();
  if (SKILL_WHITELIST.has(lower)) return true;
  if (s.length > 35) return false;
  if (DUTY_KEYWORDS.some(kw => lower.includes(kw))) return false;
  if (s.split(/\s+/).length > 4) return false;
  return true;
}

export const parseJobsTXT = async (file: File): Promise<any[]> => {
  const text = await file.text();
  const blocks = text.split(/\n\s*\n\s*\n+/);
  const jobs: any[] = [];

  for (let block of blocks) {
    block = block.trim();
    if (!block) continue;

    const lines = block.split('\n');
    let title = "";
    
    // Find the title (either starts with Job Title: or first non-empty line)
    for (let l of lines) {
       const trimmed = l.trim();
       if (trimmed) {
          if (trimmed.toLowerCase().startsWith("job title:")) {
             title = trimmed.split(":")[1].trim();
          } else if (!title) {
             title = trimmed;
          }
       }
    }
    
    if (!title) continue;

    const reqSkillsBullets: string[] = [];
    const prefSkills: string[] = [];
    let skillsRequiredLine: string[] = [];
    let currentSection = "desc";

    for (const line of lines) {
      const stripped = line.trim();
      const lower = stripped.toLowerCase();

      if (lower.includes("core requirements") || lower.includes("requirements") && !lower.includes("skills")) {
        currentSection = "req";
        continue;
      } else if (lower.includes("preferred qualifications") || lower.includes("preferred skills")) {
        currentSection = "pref";
        continue;
      } else if (lower.startsWith("skills required") || lower.startsWith("required skills")) {
        const skillsStr = stripped.includes(":") ? stripped.split(":")[1].trim() : "";
        if (skillsStr) {
          skillsRequiredLine = skillsStr.split(",").map(s => s.trim()).filter(Boolean);
        }
        currentSection = "desc";
        continue;
      } else if (lower.startsWith("skills") && !lower.includes("required")) {
         currentSection = "req"; // Assuming generic "Skills" heading implies requirements
      }

      const isBullet = stripped.startsWith("•") || stripped.startsWith("-") || stripped.startsWith("*");
      if (currentSection === "req" && isBullet) {
        reqSkillsBullets.push(stripped.replace(/^[•\-*]\s*/, '').trim());
      } else if (currentSection === "pref" && isBullet) {
        prefSkills.push(stripped.replace(/^[•\-*]\s*/, '').trim());
      }
    }

    let finalReqSkills: string[] = [];

    if (skillsRequiredLine.length > 0) {
      finalReqSkills = skillsRequiredLine;
    } else if (reqSkillsBullets.length > 0) {
      finalReqSkills = reqSkillsBullets.filter(isSkill);
    }
    
    // Deduplicate
    const seen = new Set<string>();
    const deduped: string[] = [];
    for (const s of finalReqSkills) {
       const key = s.toLowerCase();
       if (!seen.has(key)) {
          seen.add(key);
          deduped.push(s);
       }
    }

    const expMatch = block.match(/(?:minimum|min|at least)\s+(\d+)\s+years?/i);
    const rangeMatch = block.match(/(\d+)\s*-\s*(\d+)\s+years?/i);
    const plusMatch = block.match(/(\d+)\+\s+years?/i);

    let yoeMin: number | null = null;
    let yoeMax: number | null = null;

    if (rangeMatch) {
       yoeMin = parseInt(rangeMatch[1], 10);
       yoeMax = parseInt(rangeMatch[2], 10);
    } else if (expMatch) {
       yoeMin = parseInt(expMatch[1], 10);
    } else if (plusMatch) {
       yoeMin = parseInt(plusMatch[1], 10);
    }

    let seniority: string | null = null;
    const lowerDesc = block.toLowerCase();
    if (lowerDesc.includes("lead") || lowerDesc.includes("principal")) {
      seniority = "lead";
    } else if (lowerDesc.includes("senior ") || title.toLowerCase().includes("senior")) {
      seniority = "senior";
    } else if (lowerDesc.includes("mid ") || lowerDesc.includes("mid-level")) {
      seniority = "mid";
    } else if (lowerDesc.includes("junior ") || title.toLowerCase().includes("junior")) {
      seniority = "junior";
    }

    jobs.push({
      title,
      description: block,
      required_skills: deduped,
      preferred_skills: prefSkills.filter(isSkill),
      experience_years_min: yoeMin,
      experience_years_max: yoeMax,
      seniority_level: seniority
    });
  }

  return jobs;
};
