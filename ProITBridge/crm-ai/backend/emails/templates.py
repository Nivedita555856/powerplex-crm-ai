"""
templates.py — PowerPlex Email Template Library
All emails are formal, friendly, professional, and personalized.
NO email sends without passing through the approval queue.
"""
from typing import Dict, Optional
from datetime import date

COMPANY_NAME  = "PowerPlex Support"
SUPPORT_EMAIL = "niveditakothuri0506@gmail.com"
SIGNATURE     = f"\n\nWarm regards,\n{COMPANY_NAME} Team\n{SUPPORT_EMAIL}"


def ticket_confirmation(customer_name: str, ticket_id: str, issue_summary: str,
                        severity: str, product_type: str) -> Dict:
    subject = f"Support Request Received — Ticket {ticket_id}"
    body = (
        f"Dear {customer_name},\n\n"
        f"Thank you for reaching out to {COMPANY_NAME}. We have received your support request "
        f"and a ticket has been created for you.\n\n"
        f"Ticket Details:\n"
        f"  Ticket ID  : {ticket_id}\n"
        f"  Issue      : {issue_summary}\n"
        f"  Product    : {product_type}\n"
        f"  Priority   : {severity.capitalize()}\n"
        f"  Date Raised: {date.today().strftime('%d %B %Y')}\n\n"
        f"Our team will review your request and assign a specialist shortly. "
        f"We will keep you updated at every stage.\n"
        f"{'Given the critical nature of this issue, we are treating it with the highest urgency.' if severity == 'critical' else ''}"
        + SIGNATURE
    )
    return {"subject": subject, "body": body, "email_type": "ticket_confirmation"}


def technician_assignment(customer_name: str, ticket_id: str, technician_name: str,
                          technician_specialization: str, issue_summary: str,
                          estimated_date: Optional[str] = None) -> Dict:
    est = estimated_date or "within 24-48 hours"
    subject = f"Technician Assigned for Your Request — Ticket {ticket_id}"
    body = (
        f"Dear {customer_name},\n\n"
        f"We are pleased to inform you that a qualified technician has been assigned "
        f"to resolve your support request.\n\n"
        f"Assignment Details:\n"
        f"  Ticket ID      : {ticket_id}\n"
        f"  Issue          : {issue_summary}\n"
        f"  Technician     : {technician_name}\n"
        f"  Specialisation : {technician_specialization}\n"
        f"  Expected Visit : {est}\n\n"
        f"Our technician will contact you before arriving. Please ensure the appliance "
        f"is accessible and a responsible adult is present during the visit.\n\n"
        f"If you need to reschedule, please reply to this email or contact us directly."
        + SIGNATURE
    )
    return {"subject": subject, "body": body, "email_type": "technician_assignment"}


def warranty_approval(customer_name: str, ticket_id: str, appliance: str,
                      warranty_id: str, expiry_date: str, decision: str,
                      reason: Optional[str] = None) -> Dict:
    approved = decision.lower() == "approved"
    subject  = f"Warranty Claim {'Approved' if approved else 'Decision'} — {ticket_id}"
    body = (
        f"Dear {customer_name},\n\n"
        + (
            f"We are pleased to confirm that your warranty claim for your {appliance} "
            f"has been approved.\n\n"
            f"Claim Details:\n"
            f"  Ticket ID  : {ticket_id}\n"
            f"  Appliance  : {appliance}\n"
            f"  Warranty ID: {warranty_id}\n"
            f"  Valid Until: {expiry_date}\n\n"
            f"Repair or replacement (as applicable) will be processed at no cost to you. "
            f"A technician will be in touch shortly."
            if approved else
            f"After reviewing your warranty claim for your {appliance}, we regret that "
            f"we are unable to approve it under the current warranty terms.\n\n"
            f"Reason: {reason or 'Warranty period has expired or the issue is not covered under warranty terms.'}\n\n"
            f"We would be happy to assist you with a paid service visit at a competitive rate. "
            f"Please reply to this email to arrange."
        )
        + SIGNATURE
    )
    return {"subject": subject, "body": body, "email_type": "warranty_decision"}


def repair_completion(customer_name: str, ticket_id: str, appliance: str,
                      technician_name: str, resolution_notes: str) -> Dict:
    subject = f"Repair Completed — Ticket {ticket_id}"
    body = (
        f"Dear {customer_name},\n\n"
        f"We are happy to inform you that your service request has been successfully resolved.\n\n"
        f"Resolution Summary:\n"
        f"  Ticket ID  : {ticket_id}\n"
        f"  Appliance  : {appliance}\n"
        f"  Technician : {technician_name}\n"
        f"  Work Done  : {resolution_notes}\n"
        f"  Closed On  : {date.today().strftime('%d %B %Y')}\n\n"
        f"We hope your {appliance} is now working to your full satisfaction. "
        f"If you experience any further issues, please do not hesitate to reach out.\n\n"
        f"We would greatly appreciate it if you could take a moment to share your experience."
        + SIGNATURE
    )
    return {"subject": subject, "body": body, "email_type": "repair_completion"}


def escalation_notice(customer_name: str, ticket_id: str, issue_summary: str,
                      reason: str = "complexity of the issue") -> Dict:
    subject = f"Your Request Has Been Escalated — Ticket {ticket_id}"
    body = (
        f"Dear {customer_name},\n\n"
        f"We want to assure you that we are actively working on your support request. "
        f"Due to the {reason}, your ticket has been escalated to our senior support team "
        f"to ensure you receive the best possible resolution.\n\n"
        f"Ticket ID: {ticket_id}\n"
        f"Issue    : {issue_summary}\n\n"
        f"A senior specialist will be in touch with you within 4 business hours. "
        f"We sincerely apologise for any inconvenience and appreciate your patience."
        + SIGNATURE
    )
    return {"subject": subject, "body": body, "email_type": "escalation"}


def apology_email(customer_name: str, ticket_id: str, delay_reason: str) -> Dict:
    subject = f"Our Apologies — Ticket {ticket_id}"
    body = (
        f"Dear {customer_name},\n\n"
        f"We sincerely apologise for the delay in resolving your support request (Ticket {ticket_id}).\n\n"
        f"Reason for delay: {delay_reason}\n\n"
        f"We understand how important it is to have your appliance working correctly, "
        f"and we are committed to resolving your issue as quickly as possible. "
        f"Your satisfaction is our top priority.\n\n"
        f"As a gesture of goodwill, please mention this ticket number when contacting us "
        f"for any future requests to receive priority handling."
        + SIGNATURE
    )
    return {"subject": subject, "body": body, "email_type": "apology"}


def warranty_expiry_notice(customer_name: str, appliance: str,
                           expiry_date: str, upgrade_suggestions: list) -> Dict:
    subject = f"Your Warranty is Expiring — Action Recommended"
    suggestions_text = "\n".join(f"  - {s}" for s in upgrade_suggestions[:3]) or "  - Contact us for upgrade options"
    body = (
        f"Dear {customer_name},\n\n"
        f"This is a friendly reminder that the warranty on your {appliance} "
        f"is due to expire on {expiry_date}.\n\n"
        f"After this date, repair services will be chargeable. We recommend:\n"
        f"  1. Extending your warranty (if applicable)\n"
        f"  2. Scheduling a preventive maintenance visit before expiry\n"
        f"  3. Considering an upgrade to our latest models\n\n"
        f"Recommended Upgrades:\n{suggestions_text}\n\n"
        f"Reply to this email or visit our website to explore your options."
        + SIGNATURE
    )
    return {"subject": subject, "body": body, "email_type": "warranty_expiry"}


def purchase_welcome(customer_name: str, appliance: str, model: str,
                     warranty_id: str, expiry_date: str) -> Dict:
    subject = f"Welcome to PowerPlex — Thank You for Your Purchase!"
    body = (
        f"Dear {customer_name},\n\n"
        f"Thank you for choosing {COMPANY_NAME}! We are delighted to welcome you as a valued customer.\n\n"
        f"Purchase Details:\n"
        f"  Appliance   : {appliance} — {model}\n"
        f"  Warranty ID : {warranty_id}\n"
        f"  Covered Until: {expiry_date}\n\n"
        f"Getting Started:\n"
        f"  1. Register your product at our website for priority support\n"
        f"  2. Download the user manual from your customer portal\n"
        f"  3. Save our support email: {SUPPORT_EMAIL}\n\n"
        f"If you ever need assistance, our team is here 7 days a week."
        + SIGNATURE
    )
    return {"subject": subject, "body": body, "email_type": "purchase_welcome"}
