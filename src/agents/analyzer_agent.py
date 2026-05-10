from typing import Dict, Any, Optional
import difflib


class AnalyzerAgent:
    def __init__(self):
        pass

    def analyze_change(self, old_content: str, new_content: str) -> Dict[str, Any]:
        try:
            diff = list(difflib.unified_diff(
                old_content.split('\n'),
                new_content.split('\n'),
                lineterm='',
                n=3
            ))
            
            added_lines = [line[1:] for line in diff if line.startswith('+') and not line.startswith('+++')]
            removed_lines = [line[1:] for line in diff if line.startswith('-') and not line.startswith('---')]
            
            change_summary = self._generate_summary(added_lines, removed_lines)
            
            return {
                'analysis': change_summary,
                'added': added_lines[:10],
                'removed': removed_lines[:10],
                'diff_count': len(added_lines) + len(removed_lines)
            }
        
        except Exception as e:
            return {
                'analysis': f"分析错误: {str(e)}",
                'added': [],
                'removed': [],
                'diff_count': 0
            }

    def _generate_summary(self, added: list, removed: list) -> str:
        summary_parts = []
        
        if removed:
            summary_parts.append(f"删除了 {len(removed)} 行内容")
        
        if added:
            summary_parts.append(f"新增了 {len(added)} 行内容")
        
        if not summary_parts:
            return "内容无变化"
        
        summary = "; ".join(summary_parts)
        
        if removed:
            summary += f"。删除内容示例: {''.join(removed[:2]).strip()[:50]}..."
        
        if added:
            summary += f"。新增内容示例: {''.join(added[:2]).strip()[:50]}..."
        
        return summary