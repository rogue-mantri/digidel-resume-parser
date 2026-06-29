import json
import re
from datetime import datetime
from pathlib import Path

class FilterEngine:
    UNIVERSAL_RULES = [
        {'id': 'U1', 'name': 'Missing Contact Info', 'description': 'No valid email or phone number found', 'check': lambda profile: not profile.get('email') and not profile.get('phone'), 'severity': 'CRITICAL', 'action': 'REJECT'},
        {'id': 'U2', 'name': 'Generic Resume', 'description': 'Resume appears to be a template with no personalized content', 'check': lambda profile, text='': 'Your Company Name' in text or 'Your Name' in text or 'placeholder' in text.lower(), 'severity': 'HIGH', 'action': 'REJECT'},
        {'id': 'U3', 'name': 'Suspicious Experience', 'description': 'Claimed experience exceeds reasonable limits for age', 'check': lambda profile: profile.get('years_experience', 0) > 50 or profile.get('years_experience', 0) < 0, 'severity': 'HIGH', 'action': 'REJECT'},
        {'id': 'U4', 'name': 'Profanity Check', 'description': 'Resume contains inappropriate language', 'check': lambda profile, text='': any(word in text.lower() for word in ['fuck', 'shit', 'damn', 'asshole']), 'severity': 'CRITICAL', 'action': 'REJECT'},
        {'id': 'U5', 'name': 'No Skills Found', 'description': 'No recognizable skills extracted from resume', 'check': lambda profile: not profile.get('skills') or len(profile.get('skills', [])) == 0, 'severity': 'HIGH', 'action': 'REJECT'},
    ]

    ROLE_RULES = {
        'react_developer': [
            {'id': 'RD1', 'name': 'No React Experience', 'description': 'React or React.js not found in skills', 'check': lambda profile: not any('react' in s.lower() for cat in profile.get('skills', {}).values() for s in (cat if isinstance(cat, list) else [])), 'severity': 'CRITICAL', 'action': 'REJECT'},
            {'id': 'RD2', 'name': 'No JavaScript/TypeScript', 'description': 'Neither JavaScript nor TypeScript found in skills', 'check': lambda profile: not any(s.lower() in ['javascript', 'typescript', 'js', 'ts'] for cat in profile.get('skills', {}).values() for s in (cat if isinstance(cat, list) else [])), 'severity': 'CRITICAL', 'action': 'REJECT'},
            {'id': 'RD3', 'name': 'No Frontend Framework', 'description': 'No evidence of modern frontend framework', 'check': lambda profile: not any(s.lower() in ['react', 'vue', 'vue.js', 'angular', 'svelte', 'next.js', 'nextjs'] for cat in profile.get('skills', {}).values() for s in (cat if isinstance(cat, list) else [])), 'severity': 'CRITICAL', 'action': 'REJECT'},
            {'id': 'RD4', 'name': 'Seniority Mismatch', 'description': 'Applying for senior role but has < 3 years experience', 'check': lambda profile: profile.get('years_experience', 0) < 3 and 'senior' in str(profile.get('applied_for', '')).lower(), 'severity': 'HIGH', 'action': 'REJECT'},
            {'id': 'RD5', 'name': 'Backend-Only Profile', 'description': 'Only backend skills with no frontend evidence', 'check': lambda profile: not any(s.lower() in ['html', 'css', 'javascript', 'typescript', 'react', 'vue'] for cat in profile.get('skills', {}).values() for s in (cat if isinstance(cat, list) else [])), 'severity': 'HIGH', 'action': 'REJECT'},
        ],
        'uiux_designer': [
            {'id': 'UX1', 'name': 'No Design Tool', 'description': 'No mention of Figma, Adobe XD, Sketch, or equivalent', 'check': lambda profile: not any(s.lower() in ['figma', 'adobe xd', 'sketch', 'invision', 'adobe photoshop'] for cat in profile.get('skills', {}).values() for s in (cat if isinstance(cat, list) else [])), 'severity': 'CRITICAL', 'action': 'REJECT'},
            {'id': 'UX2', 'name': 'No Design Keywords', 'description': 'No UI/UX related keywords found', 'check': lambda profile: not any(word in ' '.join(s.lower() for cat in profile.get('skills', {}).values() for s in (cat if isinstance(cat, list) else [])) for word in ['ui', 'ux', 'design', 'prototype', 'wireframe']), 'severity': 'HIGH', 'action': 'REJECT'},
            {'id': 'UX3', 'name': 'Developer-Only Profile', 'description': 'Resume only shows coding skills, no design evidence', 'check': lambda profile: not any(s.lower() in ['figma', 'adobe xd', 'sketch', 'design', 'ui/ux'] for cat in profile.get('skills', {}).values() for s in (cat if isinstance(cat, list) else [])), 'severity': 'HIGH', 'action': 'REJECT'},
        ],
        'content_writer': [
            {'id': 'CW1', 'name': 'No Writing Keywords', 'description': 'No evidence of writing, content, or SEO skills', 'check': lambda profile: not any(word in ' '.join(s.lower() for cat in profile.get('skills', {}).values() for s in (cat if isinstance(cat, list) else [])) for word in ['writing', 'content', 'seo', 'copy', 'blog', 'editing']), 'severity': 'CRITICAL', 'action': 'REJECT'},
            {'id': 'CW2', 'name': 'Technical-Only Profile', 'description': 'Only coding/engineering skills, no writing', 'check': lambda profile: all(s.lower() in ['python', 'javascript', 'react', 'java', 'c++'] for cat in profile.get('skills', {}).values() for s in (cat if isinstance(cat, list) else [])), 'severity': 'HIGH', 'action': 'REJECT'},
        ],
        'intern': [
            {'id': 'IN1', 'name': 'Not Eligible for Internship', 'description': 'Has > 2 years experience or no student indication', 'check': lambda profile: profile.get('years_experience', 0) > 2, 'severity': 'HIGH', 'action': 'REJECT'},
            {'id': 'IN2', 'name': 'No Relevant Skills', 'description': 'No skills related to the intern role', 'check': lambda profile: profile.get('skills_count', 0) < 2, 'severity': 'HIGH', 'action': 'REJECT'},
            {'id': 'IN3', 'name': 'Salary Mismatch', 'description': 'Expecting full-time salary for intern role', 'check': lambda profile: profile.get('salary_expectation', 0) > 5.0, 'severity': 'MEDIUM', 'action': 'YELLOW_FLAG'},
        ],
    }

    YELLOW_FLAGS = [
        {'id': 'Y3', 'name': 'Long Notice Period', 'description': '3+ months notice period', 'check': lambda profile: profile.get('notice_period', '') and '3' in profile.get('notice_period', '')},
        {'id': 'Y5', 'name': 'No AI/Modern Tools', 'description': 'For AI-focused roles, no mention of AI tools', 'check': lambda profile: not any(word in ' '.join(profile.get('skills', {}).get('ai_tools', []) + profile.get('keywords', [])).lower() for word in ['chatgpt', 'copilot', 'cursor', 'claude', 'ai sdk', 'langchain'])},
        {'id': 'Y6', 'name': 'Low Parse Confidence', 'description': 'Parser confidence below 60%', 'check': lambda profile: profile.get('parse_confidence', 100) < 60},
    ]

    def __init__(self, role='react_developer'):
        self.role = role
        self.stats = {'processed': 0, 'passed': 0, 'rejected': 0, 'yellow_flags': 0, 'manual_review': 0}

    def evaluate(self, profile, raw_text=''):
        self.stats['processed'] += 1
        failed_rules = []
        yellow_flags = []
        for rule in self.UNIVERSAL_RULES:
            try:
                if 'text' in str(rule['check'].__code__.co_varnames):
                    triggered = rule['check'](profile, raw_text)
                else:
                    triggered = rule['check'](profile)
                if triggered:
                    failed_rules.append({'id': rule['id'], 'name': rule['name'], 'description': rule['description'], 'severity': rule['severity'], 'action': rule['action']})
            except Exception as e:
                yellow_flags.append({'id': rule['id'], 'name': f"Rule Error: {rule['name']}", 'description': f"Could not evaluate rule: {str(e)}", 'severity': 'MEDIUM'})
        role_rules = self.ROLE_RULES.get(self.role, [])
        for rule in role_rules:
            try:
                if 'text' in str(rule['check'].__code__.co_varnames):
                    triggered = rule['check'](profile, raw_text)
                else:
                    triggered = rule['check'](profile)
                if triggered:
                    failed_rules.append({'id': rule['id'], 'name': rule['name'], 'description': rule['description'], 'severity': rule['severity'], 'action': rule['action']})
            except Exception as e:
                yellow_flags.append({'id': rule['id'], 'name': f"Rule Error: {rule['name']}", 'description': f"Could not evaluate rule: {str(e)}", 'severity': 'MEDIUM'})
        for flag in self.YELLOW_FLAGS:
            try:
                if flag['check'](profile):
                    yellow_flags.append({'id': flag['id'], 'name': flag['name'], 'description': flag['description'], 'severity': flag.get('severity', 'MEDIUM')})
            except:
                pass
        critical_failures = [r for r in failed_rules if r['severity'] == 'CRITICAL']
        high_failures = [r for r in failed_rules if r['severity'] == 'HIGH']
        if critical_failures or high_failures:
            decision = 'REJECT'
            self.stats['rejected'] += 1
        elif yellow_flags:
            decision = 'YELLOW_FLAG'
            self.stats['yellow_flags'] += 1
        else:
            decision = 'PASS'
            self.stats['passed'] += 1
        confidence = self._calculate_confidence(failed_rules, yellow_flags, profile)
        return {'decision': decision, 'confidence': confidence, 'failed_rules': failed_rules, 'yellow_flags': yellow_flags, 'summary': self._generate_summary(decision, failed_rules, yellow_flags), 'evaluated_at': datetime.now().isoformat()}

    def _calculate_confidence(self, failed_rules, yellow_flags, profile):
        base = 100
        base -= (100 - profile.get('parse_confidence', 80)) * 0.5
        if any('Rule Error' in r['name'] for r in failed_rules):
            base -= 20
        total_rules = len(self.UNIVERSAL_RULES) + len(self.ROLE_RULES.get(self.role, []))
        evaluated = total_rules - len([r for r in failed_rules if 'Rule Error' in r['name']])
        if evaluated / total_rules > 0.8:
            base += 10
        return max(0, min(100, round(base, 2)))

    def _generate_summary(self, decision, failed_rules, yellow_flags):
        if decision == 'REJECT':
            reasons = [f"{r['name']}: {r['description']}" for r in failed_rules]
            return f"REJECTED — {len(failed_rules)} rule(s) failed: " + "; ".join(reasons[:3])
        elif decision == 'YELLOW_FLAG':
            warnings = [f"{f['name']}: {f['description']}" for f in yellow_flags]
            return f"YELLOW FLAG — {len(yellow_flags)} warning(s): " + "; ".join(warnings[:3])
        else:
            return "PASSED — All hard disqualifiers cleared. Candidate advances to interview."

    def get_stats(self):
        return self.stats

    def load_config(self, config_path):
        with open(config_path, 'r') as f:
            config = json.load(f)
        if 'universal_rules' in config:
            self.UNIVERSAL_RULES = config['universal_rules']
        if 'role_rules' in config:
            self.ROLE_RULES = config['role_rules']
        if 'yellow_flags' in config:
            self.YELLOW_FLAGS = config['yellow_flags']

    def save_config(self, config_path):
        config = {'universal_rules': self.UNIVERSAL_RULES, 'role_rules': self.ROLE_RULES, 'yellow_flags': self.YELLOW_FLAGS}
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
