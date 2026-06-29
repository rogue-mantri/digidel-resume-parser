import re
import json
from datetime import datetime

class StructuredParser:
    TECH_SKILLS = {
        'frontend': ['react', 'react.js', 'vue', 'vue.js', 'angular', 'svelte', 'next.js', 'nextjs', 'gatsby', 'remix', 'html', 'html5', 'css', 'css3', 'sass', 'scss', 'less', 'tailwind', 'bootstrap', 'material-ui', 'mui', 'styled-components', 'emotion', 'webpack', 'vite', 'parcel', 'babel', 'eslint', 'prettier'],
        'backend': ['node.js', 'nodejs', 'express', 'django', 'flask', 'fastapi', 'spring', 'spring boot', 'php', 'laravel', 'symfony', 'ruby on rails', 'aspnet', '.net', 'go', 'golang', 'rust', 'elixir', 'graphql', 'rest api', 'restful', 'microservices', 'serverless'],
        'languages': ['javascript', 'typescript', 'ts', 'js', 'python', 'java', 'c++', 'c#', 'csharp', 'ruby', 'php', 'go', 'golang', 'rust', 'swift', 'kotlin', 'scala', 'perl', 'shell', 'bash', 'powershell', 'sql', 'r', 'matlab'],
        'ai_ml': ['ai', 'artificial intelligence', 'machine learning', 'ml', 'deep learning', 'dl', 'neural networks', 'llm', 'large language model', 'openai', 'gpt', 'claude', 'gemini', 'anthropic', 'huggingface', 'transformers', 'langchain', 'llamaindex', 'rag', 'vector database', 'pinecone', 'weaviate', 'chromadb', 'embedding', 'fine-tuning', 'prompt engineering', 'ai sdk', 'vercel ai'],
        'databases': ['mysql', 'postgresql', 'postgres', 'mongodb', 'mongo', 'redis', 'sqlite', 'dynamodb', 'cassandra', 'elasticsearch', 'neo4j', 'firebase', 'supabase', 'prisma', 'sequelize', 'typeorm', 'sqlalchemy', 'mongoose'],
        'devops': ['docker', 'kubernetes', 'k8s', 'aws', 'amazon web services', 'azure', 'gcp', 'google cloud', 'ci/cd', 'github actions', 'jenkins', 'gitlab', 'terraform', 'ansible', 'nginx', 'apache', 'cloudflare', 'vercel', 'netlify', 'heroku'],
        'design': ['figma', 'adobe xd', 'sketch', 'invision', 'framer', 'proto.io', 'principle', 'after effects', 'photoshop', 'illustrator', 'indesign', 'canva', 'design systems', 'design tokens', 'ui/ux', 'user interface', 'user experience', 'prototyping', 'wireframing', 'user research', 'accessibility', 'wcag', 'responsive design', 'design thinking', 'information architecture', 'interaction design'],
        'content': ['seo', 'search engine optimization', 'content strategy', 'copywriting', 'blog writing', 'technical writing', 'content marketing', 'social media', 'wordpress', 'ghost', 'markdown', 'google analytics', 'ahrefs', 'semrush', 'hubspot', 'mailchimp', 'grammarly', 'jasper', 'copy.ai', 'surfer seo', 'yoast'],
        'ai_tools': ['chatgpt', 'github copilot', 'copilot', 'cursor', 'windsurf', 'claude', 'midjourney', 'dall-e', 'stable diffusion', 'runway', 'elevenlabs', 'perplexity', 'notion ai', 'gemini', 'bard', 'grok', 'replit', 'tabnine', 'codeium', 'code whisperer'],
    }
    ALL_SKILLS = set()
    for category, skills in TECH_SKILLS.items():
        ALL_SKILLS.update(skills)
    DEGREES = ['b.tech', 'b.e', 'b.e.', 'bachelor', 'bs', 'b.s', 'b.sc', 'bca', 'm.tech', 'm.e', 'master', 'ms', 'm.s', 'm.sc', 'mca', 'mba', 'phd', 'doctorate', 'diploma', 'b.com', 'b.a', 'm.com', 'm.a', 'b.pharm', 'm.pharm', 'mbbs', 'bds', 'b.arch']
    INSTITUTIONS = ['iit', 'indian institute of technology', 'nit', 'national institute of technology', 'bits', 'birla institute', 'v.j.t.i', 'vjti', 'iit bombay', 'iit delhi', 'iit madras', 'iit kharagpur', 'iit kanpur', 'iit roorkee', 'iit guwahati', 'iit hyderabad', 'iit indore', 'iit bhu', 'nit trichy', 'nit surathkal', 'nit warangal', 'iiit', 'indian institute of information technology', 'vit', 'srm', 'manipal', 'amity', 'anna university', 'jnu', 'delhi university', 'du', 'mumbai university', 'pune university']

    def __init__(self):
        self.stats = {'parsed': 0, 'failed': 0, 'fields_extracted': {}}

    def parse(self, text, file_name=''):
        try:
            raw_text = text
            result = {
                'full_name': self._extract_name(raw_text),
                'email': self._extract_email(text),
                'phone': self._extract_phone(text),
                'location': self._extract_location(text),
                'years_experience': self._extract_experience(text),
                'current_title': self._extract_current_title(text),
                'current_company': self._extract_current_company(text),
                'skills': self._extract_skills(text),
                'skills_count': 0,
                'education': self._extract_education(text),
                'keywords': self._extract_keywords(text),
                'links': self._extract_links(text),
                'salary_expectation': self._extract_salary(text),
                'notice_period': self._extract_notice_period(text),
                'parsed_at': datetime.now().isoformat(),
                'parse_confidence': 0.0
            }
            skills = result['skills']
            if isinstance(skills, dict):
                result['skills_count'] = sum(len(v) for v in skills.values())
            else:
                result['skills_count'] = len(skills)
            result['parse_confidence'] = self._calculate_confidence(result)
            self.stats['parsed'] += 1
            return result
        except Exception as e:
            self.stats['failed'] += 1
            return {'error': str(e), 'parsed_at': datetime.now().isoformat()}

    def _extract_name(self, text):
        name_patterns = [r'(?:Name|NAME)[\s]*[:\-–—][\s]*([A-Z][a-zA-Z\s]+(?:\s[A-Z][a-zA-Z]+)?)']
        for pattern in name_patterns:
            match = re.search(pattern, text, re.MULTILINE | re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                if len(name) > 3 and len(name) < 60 and not any(w in name.lower() for w in ['email', 'phone', 'address', 'linkedin']):
                    return name
        delimiters = ['\n', '  |  ', ' | ', '  •  ', ' • ', '  -  ', ' - ', '  –  ', ' – ']
        lines = [text]
        for delim in delimiters:
            new_lines = []
            for line in lines:
                new_lines.extend(line.split(delim))
            lines = new_lines
        for line in lines[:8]:
            line = line.strip()
            if re.match(r'^[A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+){1,2}$', line):
                if len(line) > 5 and len(line) < 50:
                    return line
        return None

    def _extract_email(self, text):
        pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        match = re.search(pattern, text)
        return match.group(0) if match else None

    def _extract_phone(self, text):
        patterns = [r'(?:\+91[\s\-]?)?[6-9]\d{9}', r'(?:\+91[\s\-]?)?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{4}', r'\+91\s?\d{5}\s?\d{5}', r'\+91\-\d{3}\-\d{3}\-\d{4}']
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                phone = match.group(0).strip()
                phone = re.sub(r'[^\d+]', '', phone)
                if len(phone) >= 10:
                    return phone
        return None

    def _extract_location(self, text):
        cities = ['bangalore', 'bengaluru', 'hyderabad', 'chennai', 'madras', 'mumbai', 'pune', 'delhi', 'gurgaon', 'gurugram', 'noida', 'kolkata', 'ahmedabad', 'jaipur', 'surat', 'lucknow', 'kanpur', 'nagpur', 'indore', 'thane', 'bhopal', 'visakhapatnam', 'coimbatore', 'kochi', 'mysore', 'mangalore', 'trivandrum', 'goa', 'chandigarh', 'remote', 'work from home', 'wfh']
        text_lower = text.lower()
        for city in cities:
            if city in text_lower:
                pattern = re.compile(rf'(?:Location|Address|Based in|From|Residing in|Current Location)[\s]*[:\-–—]?[\s]*([A-Za-z\s,]+(?:\s*{city}\s*[A-Za-z\s,]*))', re.IGNORECASE)
                match = pattern.search(text)
                if match:
                    loc = match.group(1).strip()
                    if len(loc) < 100:
                        return loc.title()
                return city.title()
        return None

    def _extract_experience(self, text):
        patterns = [r'(?:Total\s+)?(?:Experience|Exp)[\s]*[:\-–—]?[\s]*(\d+(?:\.\d+)?)\s*(?:years?|yrs?|Y)', r'(\d+(?:\.\d+)?)\s*(?:years?|yrs?)\s*(?:of\s+)?(?:experience|exp)', r'(?:Work\s+History|Professional\s+Experience)[\s]*[:\-]?\s*(?:\n|\s)*(\d+(?:\.\d+)?)\s*(?:years?|yrs?)']
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return float(match.group(1))
        year_pattern = re.findall(r'(?:19|20)\d{2}\s*[-–—]\s*(?:20\d{2}|present|current|now)', text, re.IGNORECASE)
        if year_pattern:
            return round(len(year_pattern) * 1.5, 1)
        return None

    def _extract_current_title(self, text):
        patterns = [r'(?:Current|Present|Most Recent)[\s]*(?:Role|Position|Title|Job)[\s]*[:\-–—]?[\s]*([A-Za-z\s]+(?:Developer|Engineer|Designer|Manager|Lead|Architect|Specialist|Consultant|Analyst|Writer|Intern)[A-Za-z\s]*)', r'(?:Current|Present)[\s]*[:\-]?\s*([A-Z][a-zA-Z\s]+(?:Developer|Engineer|Designer|Manager|Lead)[A-Za-z\s]*)']
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                title = match.group(1).strip()
                if len(title) < 80:
                    return title
        title_pattern = re.compile(r'\b(?:Senior|Junior|Lead|Principal|Staff)?\s*(?:React|Frontend|Backend|Full[\s-]?Stack|UI/UX|DevOps|Software|Cloud|AI/ML|Data|Content|Technical|Product)\s*(?:Developer|Engineer|Designer|Manager|Architect|Specialist|Writer|Analyst|Lead|Intern)\b', re.IGNORECASE)
        match = title_pattern.search(text)
        if match:
            return match.group(0).strip()
        return None

    def _extract_current_company(self, text):
        patterns = [r'(?:Current|Present|Most Recent)[\s]*(?:Company|Employer|Organization)[\s]*[:\-–—]?[\s]*([A-Za-z][A-Za-z0-9\s&.,]+)', r'(?:at|with|@)\s+([A-Z][a-zA-Z0-9\s&.,]+(?:Ltd\.?|Limited|Inc\.?|Corp\.?|Corporation|Pvt\.?|Private|LLP|GmbH|LLC)?)']
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                company = match.group(1).strip()
                if len(company) > 2 and len(company) < 80 and not company.lower() in ['present', 'current', 'now']:
                    return company
        return None

    def _extract_skills(self, text):
        text_lower = text.lower()
        skills_found = {}
        skills_section_patterns = [r'(?:^|\n)(?:Skills|Technical Skills|Technologies|Tech Stack|Tools|Expertise)[\s]*[:\-–—]?\s*(.*?)(?:\n{2,}|\n(?:Experience|Work|Education|Projects|Certifications|Professional|Summary|Achievements|References)|$)']
        skills_text = ""
        for pattern in skills_section_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                skills_text = match.group(1).lower()
                break
        if skills_text and len(skills_text) > 10:
            for category, skill_list in self.TECH_SKILLS.items():
                category_skills = []
                for skill in skill_list:
                    pattern = r'(?:^|[\s,;|•\-])' + re.escape(skill.lower()) + r'(?:[\s,;|•\-]|$)'
                    if re.search(pattern, skills_text):
                        category_skills.append(skill)
                if category_skills:
                    skills_found[category] = category_skills
        if not skills_found or sum(len(v) for v in skills_found.values()) < 3:
            for category, skill_list in self.TECH_SKILLS.items():
                category_skills = []
                for skill in skill_list:
                    if len(skill) >= 3:
                        pattern = r'(?:^|[\s,;|•\-])' + re.escape(skill.lower()) + r'(?:[\s,;|•\-]|$)'
                        if re.search(pattern, text_lower):
                            category_skills.append(skill)
                if category_skills:
                    if category in skills_found:
                        existing = set(skills_found[category])
                        skills_found[category] = list(existing.union(category_skills))
                    else:
                        skills_found[category] = category_skills
        return skills_found

    def _extract_education(self, text):
        education = []
        text_lower = text.lower()
        for degree in self.DEGREES:
            if degree in text_lower:
                education.append(degree.upper())
        institutions = []
        for inst in self.INSTITUTIONS:
            if inst.lower() in text_lower:
                institutions.append(inst.title())
        return {'degrees': list(set(education)), 'institutions': list(set(institutions))}

    def _extract_keywords(self, text):
        text_lower = text.lower()
        keywords = []
        ai_keywords = ['ai', 'artificial intelligence', 'machine learning', 'deep learning', 'llm', 'rag', 'vector database', 'fine-tuning', 'prompt engineering', 'openai', 'chatgpt', 'claude', 'anthropic', 'huggingface', 'transformers', 'langchain']
        modern_keywords = ['next.js', 'react server components', 'app router', 'turbo', 'vercel', 'supabase', 'prisma', 'tailwind', 'shadcn', 'radix', 'zustand', 'jotai', 'trpc', 'server actions', 'edge functions', 'wasm', 'webassembly']
        leadership_keywords = ['lead', 'mentor', 'architect', 'founder', 'startup', 'ownership', 'entrepreneur', 'product', 'strategy', 'vision']
        for kw in ai_keywords + modern_keywords + leadership_keywords:
            if kw in text_lower:
                keywords.append(kw)
        return list(set(keywords))

    def _extract_links(self, text):
        links = {}
        github_match = re.search(r'github\.com/[A-Za-z0-9_-]+', text)
        if github_match:
            links['github'] = 'https://' + github_match.group(0)
        linkedin_match = re.search(r'linkedin\.com/in/[A-Za-z0-9_-]+', text)
        if linkedin_match:
            links['linkedin'] = 'https://' + linkedin_match.group(0)
        portfolio_pattern = re.search(r'(?:Portfolio|Website|Personal Site)[\s]*[:\-]?[\s]*(https?://[^\s]+)', text, re.IGNORECASE)
        if portfolio_pattern:
            links['portfolio'] = portfolio_pattern.group(1)
        behance_match = re.search(r'behance\.net/[A-Za-z0-9_-]+', text)
        if behance_match:
            links['behance'] = 'https://' + behance_match.group(0)
        dribbble_match = re.search(r'dribbble\.com/[A-Za-z0-9_-]+', text)
        if dribbble_match:
            links['dribbble'] = 'https://' + dribbble_match.group(0)
        return links

    def _extract_salary(self, text):
        patterns = [r'(?:Expected|Current|CTC|Salary)[\s]*[:\-–—]?[\s]*(?:Rs\.?|₹|INR)?\s*([\d,]+(?:\.\d+)?)\s*(?:LPA|lakhs?|lpa|L|lacs?)', r'(?:Rs\.?|₹|INR)?\s*([\d,]+(?:\.\d+)?)\s*(?:LPA|lakhs?|lpa)']
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                salary_str = match.group(1).replace(',', '')
                try:
                    return float(salary_str)
                except ValueError:
                    continue
        return None

    def _extract_notice_period(self, text):
        patterns = [r'(?:Notice|NP)[\s]*[:\-–—]?[\s]*(\d+)\s*(?:months?|weeks?|days?)', r'(?:Serving|Notice)[\s]*(?:Period)?[\s]*[:\-]?[\s]*(\d+)\s*(?:months?|weeks?|days?)', r'(\d+)\s*(?:months?)\s*(?:notice|np)']
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return f"{match.group(1)} months"
        if re.search(r'\bimmediate\b|\bimmediately\b', text, re.IGNORECASE):
            return "Immediate"
        return None

    def _calculate_confidence(self, result):
        score = 0
        fields = ['full_name', 'email', 'phone', 'location', 'skills', 'years_experience']
        for field in fields:
            if result.get(field):
                score += 15
        if result.get('education', {}).get('degrees'):
            score += 10
        if result.get('links'):
            score += 10
        return min(score, 100)

    def get_stats(self):
        return self.stats
