"""Render the synthetic sample notices to PNG. Run: python scripts/render_samples.py"""
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent.parent / "samples"
OUT.mkdir(exist_ok=True)

CSS = """
body{margin:0;background:#fff;font:15px/1.5 Georgia,serif;color:#111}
.page{width:760px;padding:44px 56px;position:relative;overflow:hidden}
.wm{position:absolute;top:300px;left:-40px;transform:rotate(-24deg);font:700 54px Arial;color:rgba(200,40,40,.13);white-space:nowrap}
.hd{display:flex;justify-content:space-between;border-bottom:2px solid #111;padding-bottom:10px;margin-bottom:18px}
.ag{font:700 17px Arial}.sm{font:12.5px Arial;color:#333}
h2{font:700 18px Arial;margin:16px 0 8px;text-transform:uppercase}
.box{border:1px solid #111;padding:10px 14px;margin:12px 0}
ul{margin:6px 0}
"""

HEAD = """<div class="page"><div class="wm">SAMPLE NOTICE · SYNTHETIC DATA</div>
<div class="hd"><div><div class="ag">BAY COUNTY DEPARTMENT OF SOCIAL SERVICES</div><div class="sm">Fictional agency for testing · 100 Example Way, Bay City, CA 90000</div></div>
<div class="sm" style="text-align:right">Notice date: {date}<br>Case number: {case}<br>Program: Medi-Cal</div></div>
<p>{name}<br>[Address withheld]</p>"""

HEARING = """<h2>Your hearing rights</h2><p class="sm">If you think this action is wrong, you can ask for a State Hearing. You have 90 days from the date of this notice to ask.
If you ask before the date this action takes effect, your Medi-Cal will stay the same until a hearing decision is made. To ask, fill out the back of this page,
call 1-800-743-8525, or write to the State Hearings Division.</p></div>"""

NOTICES = {
    "ligaya": HEAD.format(date="November 2, 2026", case="BC00418827Q", name="LIGAYA R.") + """
<h2>Notice of Action: Discontinuance</h2>
<p>Your Medi-Cal will stop because we did not get the information we needed.</p>
<div class="box"><b>Effective date: November 9, 2026</b><br>Information not received: proof of income for September 2026.</div>
<p>If you send the information, we will review your case again.</p>""" + HEARING,
    "carmen": HEAD.format(date="November 2, 2026", case="BC00733105M", name="CARMEN F.") + """
<h2>Request for Information: Medi-Cal Renewal</h2>
<p>We are reviewing your Medi-Cal. We need the following information to finish your renewal:</p>
<ul><li>Pay stubs for the last 30 days</li><li>Proof of California residence (lease, utility bill, or mail)</li><li>Proof of other health insurance, if any</li></ul>
<div class="box"><b>Please return this information by November 23, 2026.</b><br>You can upload it at the county portal, mail it, fax it, or bring it to our office.</div>
<p class="sm">If you do not return the information, your Medi-Cal may stop.</p></div>""",
    "rosa": HEAD.format(date="March 3, 2027", case="BC00591262K", name="ROSA D.") + """
<h2>Notice of Noncompliance: Community Engagement</h2>
<p>We could not verify that you completed 80 hours of work or other qualifying activities in January 2027.</p>
<div class="box"><b>You must respond by April 2, 2027.</b> Send one of the following:<ul>
<li>Pay stubs for January 2027</li><li>Proof of school enrollment, job training, or volunteer hours</li><li>Proof of exemption, if you believe you are exempt</li></ul>
If we do not receive proof, your Medi-Cal will end on <b>April 30, 2027</b>.</div>
<p class="sm">Legal authority: 42 U.S.C. 1396a(xx).</p>""" + HEARING,
}

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 760, "height": 900}, device_scale_factor=1.5)
    for key, body in NOTICES.items():
        pg.set_content(f"<style>{CSS}</style>{body}")
        pg.locator(".page").screenshot(path=str(OUT / f"notice_{key}.png"))
        print("wrote", key)
    b.close()
