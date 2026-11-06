"""Synthetic sample cases. All names, case numbers, and agencies are fictional.

Each sample carries a recorded run (facts, specialist claims, drafts) so the
demo works without network access. Dates in English text use {D:RULE}
placeholders that are filled from the deterministic rules engine at runtime,
which proves the drafts and the computed deadlines can never drift apart.
"""

SAMPLES = {
    "ligaya": {
        "title": "Medi-Cal ending in 3 days",
        "client": {
            "display_name": "Ligaya R.",
            "preferred_language": "Tagalog",
            "pregnant": True,
            "pregnancy_weeks": 24,
            "children_ages": [6],
        },
        "as_of": "2026-11-06",
        "image": "samples/notice_ligaya.png",
        "facts": {
            "program": "Medi-Cal",
            "notice_type": "discontinuance",
            "notice_date": "2026-11-02",
            "effective_date": "2026-11-09",
            "response_due_date": None,
            "reason_code": "missing_information",
            "reason_text": "Your Medi-Cal will stop because we did not get the information we needed.",
            "regulations_cited": [],
            "documents_requested": ["Proof of income for September 2026"],
            "months_referenced": ["September 2026"],
            "hearing_rights_included": True,
            "language": "English",
            "agency": "Bay County Department of Social Services (fictional)",
            "case_number": "BC00418827Q",
            "topics": ["renewal", "income"],
            "plain_summary": "The county says Ligaya's Medi-Cal will stop on November 9, 2026, because it did not receive proof of her September income. She can ask for a hearing and keep her coverage while she waits.",
            "confidence": {"notice_type": 0.97, "notice_date": 0.95, "effective_date": 0.93, "response_due_date": 0.9, "documents_requested": 0.88},
            "unreadable_parts": [],
        },
        "rights": [
            {"text": "Request a State Hearing by {D:AID_PAID_PENDING} and write \"I request aid paid pending\" on the request, so Ligaya's Medi-Cal stays on while the hearing is pending. Faxing to 833-281-0905 creates a time-stamped record today.", "authority_ids": ["MC-AID-PENDING", "MC-HEARING-90"], "priority": "urgent"},
            {"text": "The action takes effect only 7 days after the notice date, which is short of the 10 days of advance notice that federal rules generally require. Raise this notice defect in the hearing request.", "authority_ids": ["MC-ADVANCE-NOTICE"], "priority": "urgent"},
            {"text": "The notice gives only a general reason and cites no regulation, which may fall short of federal notice content requirements. Ask the county to identify the specific missing item and its legal basis.", "authority_ids": ["MC-NOTICE-CONTENT"], "priority": "important"},
            {"text": "Submit the September 2026 income proof now. If coverage ends anyway, returning it by {D:RECONSIDERATION_90} lets the county reconsider eligibility without a new application.", "authority_ids": ["MC-RENEWAL"], "priority": "important"},
            {"text": "Ligaya prefers Tagalog. Request this notice and all future notices in Tagalog, plus a free interpreter for the hearing.", "authority_ids": ["LANG-ACCESS"], "priority": "helpful"},
            {"text": "The outer limit to request a hearing is {D:HEARING_90}, but waiting past the aid paid pending date risks a gap in coverage during pregnancy.", "authority_ids": ["MC-HEARING-90", "MC-AID-PENDING"], "priority": "helpful"},
        ],
        "health": [
            {"text": "Ligaya is about 24 weeks pregnant, so a coverage gap could interrupt prenatal care. If coverage lapses before the hearing request is processed, ask her prenatal clinic about same-day presumptive eligibility.", "authority_ids": ["MC-PREGNANCY"], "priority": "urgent"},
            {"text": "Remind Ligaya that any emergency department must screen and stabilize her, including if she goes into labor, regardless of her coverage status.", "authority_ids": ["US-EMTALA"], "priority": "important"},
            {"text": "Keep her next prenatal appointment on the calendar. With aid paid pending in place, her coverage continues unchanged during the hearing.", "authority_ids": ["MC-AID-PENDING", "MC-PREGNANCY"], "priority": "important"},
        ],
        "drafts": {
            "client_explanation": (
                "Magandang araw, Ligaya.\n\n"
                "Nakatanggap ka ng sulat mula sa county. Sinasabi nito na ititigil ang iyong Medi-Cal sa Lunes, Nobyembre 9, 2026, dahil hindi nila natanggap ang patunay ng iyong kita para sa Setyembre 2026.\n\n"
                "May magandang balita. May karapatan kang humiling ng State Hearing. Kapag ipinadala natin ang hiling ngayong Biyernes, Nobyembre 6, mananatili ang iyong Medi-Cal habang hinihintay ang hearing. Tuloy ang iyong mga prenatal check-up.\n\n"
                "Ito ang gagawin natin:\n"
                "1. Ipapadala namin ngayong araw ang hiling para sa hearing.\n"
                "2. Ihanda mo ang iyong mga pay stub para sa Setyembre 2026.\n"
                "3. Puwede mong hilingin na nasa Tagalog ang lahat ng sulat mula sa Medi-Cal. Libre rin ang interpreter.\n\n"
                "Kung may emergency o manganganak ka na, pumunta agad sa emergency room. Tutulungan ka nila kahit may tanong pa tungkol sa iyong coverage.\n\n"
                "Kasama mo kami sa bawat hakbang. Tawagan mo ang iyong navigator kung may tanong ka."
            ),
            "response_letter": (
                "To: California Department of Social Services, State Hearings Division\n"
                "Fax: 833-281-0905\n\n"
                "RE: Request for State Hearing and Aid Paid Pending\n"
                "Claimant: Ligaya R.\nCounty: Bay County\nProgram: Medi-Cal\nCase number: [CASE NUMBER]\nNotice date: November 2, 2026\nEffective date of action: November 9, 2026\n\n"
                "I request a State Hearing regarding the Notice of Action discontinuing my Medi-Cal benefits. I request aid paid pending, so my benefits continue unchanged until a decision is issued.\n\n"
                "Reasons for my request:\n"
                "1. The notice was dated only seven days before the effective date, which is less than the ten days of advance notice required by 42 C.F.R. § 431.211.\n"
                "2. The notice does not state the specific information that was missing or cite the regulation that supports the action, as required by 42 C.F.R. § 431.210.\n"
                "3. I am pregnant and receiving prenatal care, and a gap in coverage would harm my health and my baby's health.\n"
                "4. I am submitting proof of my September 2026 income with this request.\n\n"
                "I prefer to receive all notices in Tagalog, and I request a Tagalog interpreter for the hearing.\n\n"
                "Signature: ______________________   Date: ____________\n"
                "Phone: [PHONE NUMBER]"
            ),
            "document_checklist": [
                {"item": "Pay stubs or employer letter for September 2026", "why": "This is the information the county says it did not receive."},
                {"item": "Copy of the Notice of Action (both sides)", "why": "Attach it to the hearing request and keep a copy."},
                {"item": "Fax confirmation page or online submission receipt", "why": "This proves the hearing was requested before the effective date."},
                {"item": "Prenatal clinic name and next appointment date", "why": "This supports urgency and continuity of care."},
            ],
            "navigator_notes": "Escalation recommended because of two possible notice defects and a pregnancy. Confirm with a benefits attorney whether to argue inadequate notice in addition to submitting the income proof. File the hearing request today to secure aid paid pending.",
        },
    },
    "carmen": {
        "title": "Documents requested for renewal",
        "client": {
            "display_name": "Carmen F.",
            "preferred_language": "Spanish",
            "pregnant": False,
            "children_ages": [15],
            "notes": "Primary caregiver for her mother, who is also on Medi-Cal.",
        },
        "as_of": "2026-11-06",
        "image": "samples/notice_carmen.png",
        "facts": {
            "program": "Medi-Cal",
            "notice_type": "request_for_information",
            "notice_date": "2026-11-02",
            "effective_date": None,
            "response_due_date": "2026-11-23",
            "reason_code": "none",
            "reason_text": None,
            "regulations_cited": [],
            "documents_requested": [
                "Pay stubs for the last 30 days",
                "Proof of California residence (lease, utility bill, or mail)",
                "Proof of other health insurance, if any",
            ],
            "months_referenced": [],
            "hearing_rights_included": False,
            "language": "English",
            "agency": "Bay County Department of Social Services (fictional)",
            "case_number": "BC00733105M",
            "topics": ["renewal", "income"],
            "plain_summary": "The county needs three documents to finish Carmen's Medi-Cal renewal. They are due November 23, 2026.",
            "confidence": {"notice_type": 0.98, "notice_date": 0.96, "effective_date": 0.9, "response_due_date": 0.95, "documents_requested": 0.94},
            "unreadable_parts": [],
        },
        "rights": [
            {"text": "Return the three requested documents by {D:RFI_DUE} and keep proof of submission, such as an upload confirmation or a fax receipt.", "authority_ids": ["MC-RENEWAL"], "priority": "important"},
            {"text": "The notice allows 21 days, while federal rules require at least 30 days to return renewal information. If Carmen needs more time, ask the county in writing for the full 30 days.", "authority_ids": ["MC-RENEWAL"], "priority": "important"},
            {"text": "Carmen prefers Spanish. Request Spanish notices and a free interpreter for any phone interview.", "authority_ids": ["LANG-ACCESS"], "priority": "helpful"},
        ],
        "health": [
            {"text": "Carmen cares for her mother, who is also on Medi-Cal. Check whether her mother's renewal is due soon so the family can respond together and avoid two separate gaps in care.", "authority_ids": ["MC-RENEWAL"], "priority": "helpful"},
        ],
        "drafts": {
            "client_explanation": (
                "Hola, Carmen.\n\n"
                "El condado le envió una carta para renovar su Medi-Cal. Necesitan tres documentos antes del lunes 23 de noviembre de 2026:\n"
                "1. Sus talones de pago de los últimos 30 días.\n"
                "2. Un comprobante de domicilio en California, como su contrato de renta, un recibo de luz o una carta con su dirección.\n"
                "3. Información de cualquier otro seguro médico, si lo tiene.\n\n"
                "Si necesita más tiempo, tiene derecho a pedir hasta 30 días. También puede pedir que todas sus cartas lleguen en español y un intérprete gratis.\n\n"
                "Le ayudaremos a enviar todo y a guardar el comprobante. Estamos aquí para apoyarla."
            ),
            "response_letter": (
                "To: Bay County Department of Social Services, Medi-Cal Renewals\n\n"
                "RE: Requested renewal documents\nName: Carmen F.\nCase number: [CASE NUMBER]\nNotice date: November 2, 2026\n\n"
                "Enclosed are the documents requested in your notice dated November 2, 2026:\n"
                "1. Pay stubs for the last 30 days.\n2. Proof of California residence.\n3. Information about other health insurance, if any.\n\n"
                "Please send all future notices in Spanish. I also request a Spanish interpreter for any interview.\n\n"
                "Signature: ______________________   Date: ____________\nPhone: [PHONE NUMBER]"
            ),
            "document_checklist": [
                {"item": "Pay stubs for the last 30 days", "why": "Requested by the county to verify income."},
                {"item": "Lease, utility bill, or dated mail with her address", "why": "Requested to verify California residence."},
                {"item": "Other health insurance card, if any", "why": "Requested to coordinate coverage."},
                {"item": "Upload confirmation or fax receipt", "why": "Proves the documents were returned on time."},
            ],
            "navigator_notes": "Routine case. The notice gives 21 days, which is shorter than the federal minimum, so ask for an extension only if Carmen cannot gather the documents in time.",
        },
    },
    "rosa": {
        "title": "Work-reporting notice for a new mom",
        "client": {
            "display_name": "Rosa D.",
            "preferred_language": "Tagalog",
            "pregnant": False,
            "pregnancy_end_date": "2026-11-20",
            "children_ages": [3, 0],
        },
        "as_of": "2027-03-06",
        "simulated": True,
        "image": "samples/notice_rosa.png",
        "facts": {
            "program": "Medi-Cal",
            "notice_type": "ce_noncompliance",
            "notice_date": "2027-03-03",
            "effective_date": "2027-04-30",
            "response_due_date": "2027-04-02",
            "reason_code": "ce_hours_not_met",
            "reason_text": "We could not verify that you completed 80 hours of work or other qualifying activities in January 2027.",
            "regulations_cited": ["42 U.S.C. 1396a(xx)"],
            "documents_requested": [
                "Pay stubs for January 2027",
                "Proof of school enrollment, job training, or volunteer hours",
                "Proof of exemption, if you believe you are exempt",
            ],
            "months_referenced": ["January 2027"],
            "hearing_rights_included": True,
            "language": "English",
            "agency": "Bay County Department of Social Services (fictional)",
            "case_number": "BC00591262K",
            "topics": ["community_engagement"],
            "plain_summary": "The county says Rosa did not show 80 hours of work or other activities in January 2027, and her Medi-Cal could end on April 30, 2027. She has until April 2, 2027, to send proof of hours or proof that she is exempt.",
            "confidence": {"notice_type": 0.96, "notice_date": 0.97, "effective_date": 0.95, "response_due_date": 0.94, "documents_requested": 0.91},
            "unreadable_parts": [],
        },
        "rights": [
            {"text": "Rosa appears exempt on two independent grounds: she is within the postpartum period, and she is the parent of children age 13 or younger. Respond by {D:CE_RESPONSE_30} claiming both exemptions with proof.", "authority_ids": ["MC-CE-EXEMPT", "MC-CE-NONCOMPLIANCE"], "priority": "urgent"},
            {"text": "Coverage continues during the 30-day response period, and the county must consider every other basis for eligibility before ending coverage.", "authority_ids": ["MC-CE-NONCOMPLIANCE"], "priority": "important"},
            {"text": "If the county does not accept the exemption, request a State Hearing by {D:AID_PAID_PENDING} to keep coverage in place while the hearing is decided.", "authority_ids": ["MC-AID-PENDING", "MC-HEARING-90"], "priority": "important"},
            {"text": "Rosa prefers Tagalog. Request Tagalog notices and a free interpreter for any interview or hearing.", "authority_ids": ["LANG-ACCESS"], "priority": "helpful"},
        ],
        "health": [
            {"text": "Rosa is about three months postpartum. Medi-Cal postpartum coverage continues for 12 months after pregnancy ends, which protects her postpartum checkups and mental health care.", "authority_ids": ["MC-POSTPARTUM-12"], "priority": "urgent"},
            {"text": "Make sure Rosa knows that postpartum depression screening and breastfeeding support, including a breast pump, are covered preventive services.", "authority_ids": ["US-ACA-PREVENTIVE"], "priority": "important"},
        ],
        "drafts": {
            "client_explanation": (
                "Magandang araw, Rosa.\n\n"
                "Nakatanggap ka ng sulat tungkol sa bagong patakaran ng Medi-Cal na nangangailangan ng 80 oras ng trabaho o ibang gawain bawat buwan. Sinasabi ng county na hindi nila nakita ang iyong mga oras para sa Enero 2027.\n\n"
                "May magandang balita. Mukhang exempt ka, ibig sabihin, hindi para sa iyo ang patakarang ito. Bagong panganak ka pa lamang, at may anak kang edad 13 pababa. Parehong dahilan ito para ma-exempt.\n\n"
                "Ito ang gagawin natin bago ang Biyernes, Abril 2, 2027:\n"
                "1. Ipapadala namin ang sulat na nagsasabing exempt ka.\n"
                "2. Ihanda mo ang birth certificate o hospital record ng iyong bunso.\n"
                "3. Ihanda mo rin ang birth certificate ng iyong anak na tatlong taong gulang.\n\n"
                "Habang hinihintay ang sagot, tuloy ang iyong Medi-Cal. Tuloy rin ang iyong postpartum check-up at ang tulong para sa pagpapasuso.\n\n"
                "Kasama mo kami. Tawagan mo ang iyong navigator kung may tanong ka."
            ),
            "response_letter": (
                "To: Bay County Department of Social Services, Medi-Cal Community Engagement Unit\n\n"
                "RE: Response to Notice of Noncompliance dated March 3, 2027\nName: Rosa D.\nCase number: [CASE NUMBER]\n\n"
                "I am writing in response to your notice dated March 3, 2027. I am exempt from the Medi-Cal community engagement requirement for two independent reasons:\n\n"
                "1. Postpartum exemption. My pregnancy ended on November 20, 2026, and I am within the postpartum period.\n"
                "2. Parent or caregiver exemption. I am the parent and caregiver of two children age 13 or younger.\n\n"
                "Enclosed are my child's birth record and my older child's birth certificate. Please update my case to reflect these exemptions and continue my Medi-Cal coverage.\n\n"
                "Please send all future notices in Tagalog. I also request a Tagalog interpreter for any interview.\n\n"
                "Signature: ______________________   Date: ____________\nPhone: [PHONE NUMBER]"
            ),
            "document_checklist": [
                {"item": "Newborn's birth certificate or hospital discharge record", "why": "Proves the postpartum exemption."},
                {"item": "Older child's birth certificate", "why": "Proves the parent or caregiver exemption."},
                {"item": "Copy of the noncompliance notice", "why": "Attach to the response and keep a copy."},
                {"item": "Submission receipt", "why": "Proves the response was sent within the 30-day window."},
            ],
            "navigator_notes": "Two exemptions apply, so this notice likely went out in error. Submit the exemption response first. Calendar the hearing date only as a backup if the county does not update the case.",
        },
    },
}
