"""
reporting.py — PDF Report Generation for FocusFlow Phase 2.
Uses fpdf2 to create professional neurofeedback progress reports.
"""

import logging
import io
import math
from datetime import datetime
from typing import List, Dict

logger = logging.getLogger('FocusFlow.Report')


def _safe(text: str) -> str:
    """Sanitize text for fpdf2 Helvetica (Latin-1 only). Replace Unicode with ASCII."""
    replacements = {
        '\u2192': '->', '\u2190': '<-', '\u2194': '<->',  # arrows
        '\u2014': '--', '\u2013': '-',                       # em/en dash
        '\u2018': "'", '\u2019': "'",                        # smart single quotes
        '\u201c': '"', '\u201d': '"',                        # smart double quotes
        '\u2026': '...', '\u2022': '*',                      # ellipsis, bullet
        '\u00b0': 'deg',                                     # degree
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    # Strip any remaining non-Latin1 characters
    return text.encode('latin-1', errors='replace').decode('latin-1')


def generate_pdf_report(student: Dict, sessions: List[Dict]) -> bytes:
    """
    Generate a professional PDF report for a student.
    
    Args:
        student: dict with name, roll_no, class_name, college_name, age
        sessions: list of session dicts (score_focus, score_peak, duration_sec, created_at)
    
    Returns:
        PDF as bytes
    """
    try:
        from fpdf import FPDF
    except ImportError:
        logger.error("fpdf2 not installed. Run: pip install fpdf2")
        return b""

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # -- Header --
    pdf.set_fill_color(15, 15, 40)
    pdf.rect(0, 0, 210, 35, 'F')
    pdf.set_text_color(100, 200, 255)
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_y(8)
    pdf.cell(0, 10, "FocusFlow", ln=True, align="C")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(180, 180, 220)
    pdf.cell(0, 6, "Neurofeedback Progress Report", ln=True, align="C")
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 5, f"Generated: {datetime.now().strftime('%d %B %Y, %I:%M %p')}", ln=True, align="C")

    # -- Student Info --
    pdf.set_y(42)
    pdf.set_fill_color(230, 240, 255)
    pdf.set_draw_color(100, 150, 220)
    pdf.set_text_color(20, 20, 60)
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "Student Information", ln=True, fill=True)
    pdf.ln(2)

    pdf.set_font("Helvetica", "", 11)
    info_rows = [
        ("Name", _safe(student.get("name", "N/A"))),
        ("Roll No", _safe(student.get("roll_no", "N/A"))),
        ("Age", _safe(str(student.get("age", "N/A")))),
        ("Class", _safe(student.get("class_name", "N/A"))),
        ("School / College", _safe(student.get("college_name", "N/A"))),
        ("Total Sessions", str(len(sessions))),
    ]
    for label, value in info_rows:
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(50, 7, f"  {label}:", border=0)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 7, value, border=0, ln=True)

    # -- Summary Stats --
    if sessions:
        avg_focuses = [s.get("score_focus", 0) for s in sessions]
        peak_focuses = [s.get("score_peak", 0) for s in sessions]
        durations = [s.get("duration_sec", 0) for s in sessions]

        overall_avg = sum(avg_focuses) / len(avg_focuses)
        overall_peak = max(peak_focuses)
        total_time = sum(durations)
        first_session_focus = avg_focuses[-1] if len(avg_focuses) > 1 else avg_focuses[0]
        last_session_focus = avg_focuses[0]
        improvement = last_session_focus - first_session_focus

        pdf.ln(6)
        pdf.set_fill_color(230, 240, 255)
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 8, "Performance Summary", ln=True, fill=True)
        pdf.ln(2)

        stats = [
            ("Average Focus Score", f"{overall_avg:.1f}%"),
            ("Peak Focus Score", f"{overall_peak:.1f}%"),
            ("Total Session Time", f"{total_time // 60} min {total_time % 60} sec"),
            ("Improvement", f"{improvement:+.1f}% (first -> latest)"),
        ]
        for label, value in stats:
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(70, 7, f"  {label}:", border=0)
            pdf.set_font("Helvetica", "", 10)
            color = (0, 150, 50) if "Improvement" in label and improvement >= 0 else (200, 50, 50)
            pdf.set_text_color(*color)
            pdf.cell(0, 7, value, border=0, ln=True)
            pdf.set_text_color(20, 20, 60)

        # -- Focus Trend Text Chart --
        pdf.ln(6)
        pdf.set_fill_color(230, 240, 255)
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 8, "Focus Trend (Session by Session)", ln=True, fill=True)
        pdf.ln(3)

        bar_max_width = 130
        for i, sess in enumerate(reversed(sessions)):  # Oldest first
            focus = sess.get("score_focus", 0)
            date_raw = sess.get("created_at", "")
            try:
                date_str = datetime.fromisoformat(date_raw.replace("Z", "+00:00")).strftime("%d/%m/%Y")
            except Exception:
                date_str = f"Session {i+1}"

            bar_width = int((focus / 100.0) * bar_max_width)
            bar_width = max(bar_width, 2)

            if focus >= 70:
                rgb = (50, 200, 100)
            elif focus >= 45:
                rgb = (255, 165, 0)
            else:
                rgb = (220, 60, 60)

            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(80, 80, 80)
            pdf.cell(28, 5, _safe(date_str), border=0)
            pdf.set_fill_color(*rgb)
            pdf.cell(bar_width, 5, "", border=0, fill=True)
            pdf.set_text_color(30, 30, 30)
            pdf.cell(0, 5, f" {focus:.1f}%", border=0, ln=True)
            pdf.ln(1)
            
            if pdf.get_y() > 265:
                pdf.add_page()

        # -- Session History Table --
        pdf.ln(6)
        pdf.set_fill_color(230, 240, 255)
        pdf.set_text_color(20, 20, 60)
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 8, "Session History", ln=True, fill=True)
        pdf.ln(2)

        pdf.set_font("Helvetica", "B", 9)
        pdf.set_fill_color(200, 220, 255)
        headers = ["#", "Date", "Duration", "Avg Focus", "Peak Focus"]
        widths = [10, 45, 35, 40, 40]
        for h, w in zip(headers, widths):
            pdf.cell(w, 7, h, border=1, fill=True, align="C")
        pdf.ln()

        pdf.set_font("Helvetica", "", 9)
        for i, sess in enumerate(sessions):
            date_raw = sess.get("created_at", "")
            try:
                date_str = datetime.fromisoformat(date_raw.replace("Z", "+00:00")).strftime("%d %b %Y")
            except Exception:
                date_str = "Unknown"
            dur = sess.get("duration_sec", 0)
            dur_str = f"{dur // 60}m {dur % 60}s"
            avg_f = sess.get("score_focus", 0)
            peak_f = sess.get("score_peak", 0)

            fill = (245, 248, 255) if i % 2 == 0 else (255, 255, 255)
            pdf.set_fill_color(*fill)
            row = [str(i+1), _safe(date_str), dur_str, f"{avg_f:.1f}%", f"{peak_f:.1f}%"]
            for val, w in zip(row, widths):
                pdf.cell(w, 6, val, border=1, fill=True, align="C")
            pdf.ln()

            if pdf.get_y() > 265:
                pdf.add_page()

    # -- Footer --
    pdf.ln(8)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 5, "This report is generated by FocusFlow -- Research-Grade Neurofeedback System.", ln=True, align="C")
    pdf.cell(0, 5, "Data is based on EEG (Muse 2) measurements and is for wellness purposes only.", ln=True, align="C")

    return bytes(pdf.output())
