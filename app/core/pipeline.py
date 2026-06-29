import os
import sys
import json
import csv
import argparse
from datetime import datetime
from pathlib import Path

from extractor import ResumeExtractor
from structured_parser import StructuredParser
from filter_engine import FilterEngine

class Pipeline:
    def __init__(self, role='react_developer', output_dir='output'):
        self.role = role
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.extractor = ResumeExtractor()
        self.parser = StructuredParser()
        self.filter = FilterEngine(role=role)
        self.results = []
        self.batch_stats = {'started_at': datetime.now().isoformat(), 'total_files': 0, 'successfully_parsed': 0, 'failed_parsing': 0, 'passed_filter': 0, 'rejected': 0, 'yellow_flags': 0}

    def process_file(self, file_path):
        file_path = Path(file_path)
        print(f"\nProcessing: {file_path.name}")
        extraction = self.extractor.extract(file_path)
        if not extraction['success']:
            print(f"  ❌ EXTRACTION FAILED: {extraction.get('error', 'Unknown error')}")
            self.batch_stats['failed_parsing'] += 1
            return {'file_name': file_path.name, 'status': 'EXTRACTION_FAILED', 'error': extraction.get('error', 'Unknown')}
        print(f"  ✓ Text extracted ({len(extraction['text'])} chars)")
        profile = self.parser.parse(extraction['text'], file_path.name)
        if 'error' in profile:
            print(f"  ❌ PARSING FAILED: {profile['error']}")
            self.batch_stats['failed_parsing'] += 1
            return {'file_name': file_path.name, 'status': 'PARSING_FAILED', 'error': profile['error']}
        print(f"  ✓ Parsed: {profile.get('full_name', 'Unknown')} | Skills: {len(profile.get('skills', []))} | Confidence: {profile.get('parse_confidence', 0)}%")
        filter_result = self.filter.evaluate(profile, extraction['text'])
        decision = filter_result['decision']
        if decision == 'PASS':
            print(f"  ✅ FILTER PASS (Confidence: {filter_result['confidence']}%)")
            self.batch_stats['passed_filter'] += 1
        elif decision == 'REJECT':
            print(f"  ❌ FILTER REJECT (Confidence: {filter_result['confidence']}%)")
            for rule in filter_result['failed_rules'][:2]: print(f"     → {rule['id']}: {rule['name']}")
            self.batch_stats['rejected'] += 1
        else:
            print(f"  ⚠️  YELLOW FLAG (Confidence: {filter_result['confidence']}%)")
            for flag in filter_result['yellow_flags'][:2]: print(f"     → {flag['id']}: {flag['name']}")
            self.batch_stats['yellow_flags'] += 1
        result = {'file_name': file_path.name, 'file_path': str(file_path), 'status': 'SUCCESS', 'extraction': {'format': extraction['format'], 'file_size': extraction['file_size'], 'text_length': len(extraction['text'])}, 'profile': profile, 'filter_result': filter_result}
        self.results.append(result)
        self.batch_stats['successfully_parsed'] += 1
        return result

    def process_folder(self, folder_path, recursive=False):
        folder = Path(folder_path)
        pattern = '**/*' if recursive else '*'
        files = [f for f in folder.glob(pattern) if f.suffix.lower() in ResumeExtractor.SUPPORTED_FORMATS]
        self.batch_stats['total_files'] = len(files)
        print(f"\n{'='*60}\nDIGIDELSOLUTIONS RESUME PIPELINE\nRole: {self.role}\nFolder: {folder}\nFiles found: {len(files)}\n{'='*60}\n")
        for file_path in files:
            self.process_file(file_path)
        self.batch_stats['completed_at'] = datetime.now().isoformat()
        self._generate_reports()
        self._print_summary()
        return self.results

    def _generate_reports(self):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        json_path = self.output_dir / f"pipeline_results_{timestamp}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump({'batch_stats': self.batch_stats, 'extractor_stats': self.extractor.get_stats(), 'parser_stats': self.parser.get_stats(), 'filter_stats': self.filter.get_stats(), 'results': self.results}, f, indent=2, ensure_ascii=False, default=str)
        print(f"\n📄 Detailed report saved: {json_path}")
        csv_path = self.output_dir / f"pipeline_summary_{timestamp}.csv"
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['File Name', 'Name', 'Email', 'Phone', 'Experience (Years)', 'Current Title', 'Skills Count', 'AI Skills', 'Decision', 'Confidence', 'Failed Rules', 'Yellow Flags', 'Parse Confidence'])
            for r in self.results:
                if r['status'] != 'SUCCESS':
                    writer.writerow([r['file_name'], 'N/A', 'N/A', 'N/A', 'N/A', 'N/A', 0, 'No', 'EXTRACTION_FAILED', 0, r.get('error', ''), '', 0])
                    continue
                profile = r['profile']
                filter_res = r['filter_result']
                skills = profile.get('skills', [])
                ai_skills = [s for s in skills if any(ai in s.lower() for ai in ['ai', 'llm', 'chatgpt', 'copilot', 'rag'])]
                writer.writerow([r['file_name'], profile.get('full_name', 'N/A'), profile.get('email', 'N/A'), profile.get('phone', 'N/A'), profile.get('years_experience', 'N/A'), profile.get('current_title', 'N/A'), len(skills), 'Yes' if ai_skills else 'No', filter_res['decision'], f"{filter_res['confidence']}%", '; '.join([rule['id'] for rule in filter_res['failed_rules']]), '; '.join([flag['id'] for flag in filter_res['yellow_flags']]), f"{profile.get('parse_confidence', 0)}%"])
        print(f"📄 CSV summary saved: {csv_path}")
        pass_csv_path = self.output_dir / f"pipeline_passed_{timestamp}.csv"
        passed_results = [r for r in self.results if r['status'] == 'SUCCESS' and r['filter_result']['decision'] == 'PASS']
        with open(pass_csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['File Name', 'Name', 'Email', 'Phone', 'Experience (Years)', 'Current Title', 'Skills', 'Keywords', 'Links', 'Decision'])
            for r in passed_results:
                profile = r['profile']
                writer.writerow([r['file_name'], profile.get('full_name', 'N/A'), profile.get('email', 'N/A'), profile.get('phone', 'N/A'), profile.get('years_experience', 'N/A'), profile.get('current_title', 'N/A'), ', '.join(profile.get('skills', [])), ', '.join(profile.get('keywords', [])), json.dumps(profile.get('links', {})), 'PASS'])
        print(f"📄 PASS-only CSV saved: {pass_csv_path} ({len(passed_results)} candidates)")

    def _print_summary(self):
        print(f"\n{'='*60}\nPIPELINE SUMMARY\n{'='*60}\nTotal files:     {self.batch_stats['total_files']}\nSuccessfully parsed: {self.batch_stats['successfully_parsed']}\nFailed parsing:  {self.batch_stats['failed_parsing']}\nPassed filter:   {self.batch_stats['passed_filter']}\nRejected:        {self.batch_stats['rejected']}\nYellow flags:    {self.batch_stats['yellow_flags']}\n{'='*60}\nOutput directory: {self.output_dir}\n{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description='Digidelsolutions Resume Parser & Filter Pipeline')
    parser.add_argument('input', help='Path to resume file or folder')
    parser.add_argument('--role', '-r', default='react_developer', choices=['react_developer', 'uiux_designer', 'content_writer', 'intern'], help='Role to filter for (default: react_developer)')
    parser.add_argument('--output', '-o', default='output', help='Output directory (default: output)')
    parser.add_argument('--recursive', '-R', action='store_true', help='Process subdirectories recursively')
    args = parser.parse_args()
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Path not found: {input_path}")
        sys.exit(1)
    pipeline = Pipeline(role=args.role, output_dir=args.output)
    if input_path.is_file():
        pipeline.process_file(input_path)
    else:
        pipeline.process_folder(input_path, recursive=args.recursive)

if __name__ == '__main__':
    main()
