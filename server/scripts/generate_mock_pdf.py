"""Generate a mock MOE School Property Management Handbook PDF for testing RAG."""
import os
import textwrap
from fpdf import FPDF


SECTIONS = [
    ("Section 1: Introduction to School Property Management",
     """The Ministry of Education (MOE) is the owner of most state school property in New Zealand. School boards are responsible for the day-to-day management and maintenance of their school property. This handbook provides guidance on roles, responsibilities, and processes for effective property management.

Key terminology:
- 5YA (5 Year Agreement): A funding agreement between MOE and schools for planned property improvements over a 5-year cycle.
- 10YPP (10 Year Property Plan): A long-term strategic plan that identifies all property needs for the next decade.
- SFIS (School Financial Information System): The system used for property funding applications.
- Iwi Consultation: Engagement with local Maori iwi regarding property developments that may affect cultural sites."""),

    ("Section 2: Roles and Responsibilities",
     """2.1 School Board Responsibilities:
- Maintain all buildings, grounds, and infrastructure in a safe condition
- Complete day-to-day maintenance using operational funding
- Report any significant damage or health and safety issues to MOE within 5 working days
- Develop and maintain a 10 Year Property Plan (10YPP)
- Ensure compliance with Building Code and relevant NZ Standards

2.2 Ministry of Education Responsibilities:
- Provide capital funding for major upgrades and new builds
- Administer the 5YA programme
- Approve projects over $100,000 in value
- Conduct condition assessments every 5 years
- Provide emergency funding for natural disasters"""),

    ("Section 3: The 5 Year Agreement (5YA) Programme",
     """3.1 Overview:
The 5YA is a bulk funding agreement that provides schools with a guaranteed amount of property funding over a 5-year period. Schools have flexibility in how they prioritise and spend this funding within MOE guidelines.

3.2 Eligibility:
All state and state-integrated schools with a roll of 50 or more students are eligible for the 5YA programme. Smaller schools receive property funding through the Isolated Schools Property Programme.

3.3 Funding Allocation:
5YA funding is calculated based on: school roll (number of students), age and condition of buildings, geographic location and climate factors, and seismic risk profile.

3.4 Approved Uses of 5YA Funding:
- Roof replacements and repairs
- Interior modernisation (painting, flooring, fixtures)
- Electrical and plumbing upgrades
- Weathertightness remediation
- Health and safety compliance work
- Heating and ventilation improvements

3.5 Restrictions:
5YA funding CANNOT be used for: new buildings or additional teaching spaces, swimming pools, land purchases, or furniture and equipment."""),

    ("Section 4: Maintenance Priority Classification",
     """All maintenance and repair work must be classified according to the following MOE Priority Levels:

Priority 1 - CRITICAL (Immediate action required):
Definition: Presents an immediate risk to health and safety of occupants.
Response time: Within 24 hours.
Examples: Structural failure, exposed asbestos, gas leak, major electrical fault, fire damage making area unsafe.

Priority 2 - URGENT (Action required within 3 months):
Definition: Will deteriorate to Priority 1 if not addressed, or significantly impacts the learning environment.
Response time: Within 3 months.
Examples: Active roof leak causing interior damage, failed heating system in winter, broken windows creating security risk, significant mould growth.

Priority 3 - NECESSARY (Action required within 12 months):
Definition: Component is nearing end of life or has minor defects that do not pose immediate risk.
Response time: Within 12 months.
Examples: Aging roof with no active leaks, worn carpet creating trip hazard, outdated electrical switchboard, peeling exterior paint.

Priority 4 - DESIRABLE (Plan within next 5YA cycle):
Definition: Improvement that enhances functionality or aesthetics but is not required for safety or compliance.
Response time: Next 5YA cycle (1-5 years).
Examples: Modernising classroom layout, upgrading lighting to LED, landscaping improvements, technology infrastructure upgrades."""),

    ("Section 5: Reporting and Compliance",
     """5.1 Annual Property Report:
Schools must submit an annual property report to MOE by 31 March each year. This report must include: summary of maintenance work completed, 5YA expenditure breakdown, updated condition assessment of all buildings, and planned work for the coming year.

5.2 Health and Safety Compliance:
Schools must comply with: Health and Safety at Work Act 2015, Building Act 2004 and NZ Building Code, Education (Physical Restraint) Rules 2023, and Asbestos Management Regulations.

5.3 Emergency Procedures:
In the event of an emergency (earthquake, flood, fire):
1. Ensure safety of all occupants
2. Contact MOE Emergency Response Team: 0800 MOE HELP
3. Document damage with photographs
4. Do not re-enter damaged buildings until cleared by engineer
5. Submit emergency funding application within 10 working days"""),

    ("Section 6: Iwi Consultation Requirements",
     """6.1 When Consultation is Required:
Schools must consult with local iwi when: any earthworks or excavation is planned on school grounds, new buildings are proposed near known cultural or heritage sites, trees of cultural significance may be affected, or the project involves modification to buildings with heritage status.

6.2 Process:
1. Identify relevant iwi through local council or Te Puni Kokiri
2. Provide project plans at least 20 working days before work begins
3. Hold a hui if requested by iwi representatives
4. Document any agreed conditions or cultural monitoring requirements
5. Include iwi consultation records in project documentation

6.3 Accidental Discovery Protocol:
If cultural artefacts or koiwi (human remains) are discovered during work: stop all work immediately, secure the area, contact local iwi and Heritage New Zealand, do not resume work until clearance is given."""),
]


def generate_pdf():
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=25)
    pdf.set_margins(25, 25, 25)
    width = 210 - 50  # A4 width minus margins

    # Title page
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.ln(60)
    pdf.cell(width, 10, "MOE School Property Management", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(width, 10, "Handbook", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(10)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(width, 7, "Ministry of Education | Te Tahuhu o te Matauranga", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(width, 7, "Version 2.3 - March 2026", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)
    pdf.set_font("Helvetica", "I", 9)
    pdf.cell(width, 7, "MOCK DOCUMENT FOR DEVELOPMENT TESTING ONLY", align="C", new_x="LMARGIN", new_y="NEXT")

    # Content
    for heading, body in SECTIONS:
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(width, 8, heading, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)
        pdf.set_font("Helvetica", "", 10)

        for paragraph in body.split("\n"):
            if not paragraph.strip():
                pdf.ln(3)
                continue
            # Wrap long lines manually to avoid fpdf issues
            wrapped = textwrap.wrap(paragraph, width=95)
            for line in wrapped:
                pdf.cell(width, 5, line, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)

    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "MOE_Property_Management_Handbook_Mock.pdf")
    pdf.output(output_path)
    print(f"Generated: {output_path} ({pdf.page} pages)")


if __name__ == "__main__":
    generate_pdf()
