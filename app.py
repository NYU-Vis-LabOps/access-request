from datetime import datetime
from enum import StrEnum
import os
from pathlib import Path
import uuid
from typing import Iterable, List

from flask import Flask, jsonify, redirect, render_template, request, send_from_directory, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///access_requests.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = str(Path(app.instance_path) / "uploads")
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

db = SQLAlchemy(app)


class RequestStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    DEFERRED = "deferred"


class AccessRequest(db.Model):  # type: ignore[misc]
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    first_name = db.Column(db.String(80), nullable=False, default="")
    last_name = db.Column(db.String(80), nullable=False, default="")
    applicant_email = db.Column(db.String(255), nullable=False)
    applicant_role = db.Column(db.String(32), nullable=True)
    applicant_department = db.Column(db.String(120), nullable=True)
    space_department = db.Column(db.String(120), nullable=True)
    departments = db.Column(db.Text, nullable=True)  # comma-separated list
    nyu_id = db.Column(db.String(32), nullable=False)
    n_number = db.Column(db.String(32), nullable=False)
    building = db.Column(db.String(120), nullable=False)
    room_numbers = db.Column(db.String(255), nullable=False)
    access_start_date = db.Column(db.String(32), nullable=False, default="")
    access_end_date = db.Column(db.String(32), nullable=False, default="")
    access_type = db.Column(db.String(80), nullable=False, default="")
    attachment_filename = db.Column(db.String(255), nullable=True)

    pi_email = db.Column(db.String(255), nullable=True)
    approver_emails = db.Column(db.Text, nullable=True)  # comma-separated list

    status = db.Column(db.String(32), nullable=False, default=RequestStatus.PENDING.value)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    last_action_by = db.Column(db.String(255), nullable=True)
    last_action_note = db.Column(db.Text, nullable=True)

    def approver_list(self) -> List[str]:
        if not self.approver_emails:
            return []
        return [email.strip() for email in self.approver_emails.split(",") if email.strip()]


def send_email(to_addrs: Iterable[str], subject: str, body: str) -> None:
    """Placeholder email sender for demo purposes."""
    recipients = ", ".join(to_addrs)
    print(f"[EMAIL] To: {recipients}\nSubject: {subject}\n\n{body}\n")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/submit", methods=["POST"])
def submit():
    """Handle building access request submission."""
    first_name = request.form.get("first_name", "").strip()
    last_name = request.form.get("last_name", "").strip()
    name = " ".join([part for part in [first_name, last_name] if part]).strip()
    applicant_email = request.form.get("applicant_email", "").strip()
    applicant_role = request.form.get("applicant_role", "").strip()
    applicant_department = request.form.get("applicant_department", "").strip()
    space_department = request.form.get("space_department", "").strip()
    departments = request.form.get("departments", "").strip()
    nyu_id = request.form.get("nyu_id", "").strip()
    n_number = request.form.get("n_number", "").strip()
    building = request.form.get("building", "").strip()
    room_numbers = request.form.get("room_numbers", "").strip()
    access_start_date = request.form.get("access_start_date", "").strip()
    access_end_date = request.form.get("access_end_date", "").strip()
    access_type = request.form.get("access_type", "").strip()
    uploaded_file = request.files.get("attachment")
    pi_email = request.form.get("pi_email", "").strip()
    approvers_raw = request.form.get("approver_emails", "").strip()

    approver_emails = ",".join(
        [email.strip() for email in approvers_raw.split(",") if email.strip()]
    )

    attachment_filename = None
    if uploaded_file and uploaded_file.filename:
        safe_name = secure_filename(uploaded_file.filename)
        if safe_name:
            unique_name = f"{uuid.uuid4().hex}_{safe_name}"
            target_path = Path(app.config["UPLOAD_FOLDER"]) / unique_name
            uploaded_file.save(target_path)
            attachment_filename = unique_name

    req = AccessRequest(
        name=name,
        first_name=first_name,
        last_name=last_name,
        applicant_email=applicant_email,
        applicant_role=applicant_role or None,
        applicant_department=applicant_department or None,
        space_department=space_department or None,
        departments=(space_department or departments) or None,
        nyu_id=nyu_id,
        n_number=n_number,
        building=building,
        room_numbers=room_numbers,
        access_start_date=access_start_date,
        access_end_date=access_end_date,
        access_type=access_type,
        attachment_filename=attachment_filename,
        pi_email=pi_email or None,
        approver_emails=approver_emails or None,
    )
    db.session.add(req)
    db.session.commit()

    # Notify approvers and PI (demo only)
    recipients: List[str] = req.approver_list()
    if req.pi_email:
        recipients.append(req.pi_email)
    if recipients:
        subject = f"[Access Request] {req.name} - {req.building}"
        body = (
            f"A new building access request has been submitted.\n\n"
            f"Name: {req.name}\n"
            f"Applicant Email: {req.applicant_email}\n"
            f"Applicant Role: {req.applicant_role or 'N/A'}\n"
            f"Applicant Department: {req.applicant_department or 'N/A'}\n"
            f"Space Department: {req.space_department or req.departments or 'N/A'}\n"
            f"NYU ID: {req.nyu_id}\n"
            f"N#: {req.n_number}\n"
            f"Building: {req.building}\n"
            f"Room(s): {req.room_numbers}\n"
            f"Access Start Date: {req.access_start_date}\n"
            f"Access End Date: {req.access_end_date}\n"
            f"Access Type: {req.access_type}\n"
            f"Attachment: {req.attachment_filename or 'N/A'}\n"
            f"Status: {req.status}\n\n"
            f"To review this request, visit: {url_for('approver_portal', _external=True)}"
        )
        send_email(recipients, subject, body)

    return jsonify({"success": True, "id": req.id})


@app.route("/requests")
def list_requests():
    """View and search access requests."""
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()

    query = AccessRequest.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(
                AccessRequest.name.ilike(like),
                AccessRequest.first_name.ilike(like),
                AccessRequest.last_name.ilike(like),
                AccessRequest.applicant_email.ilike(like),
                AccessRequest.applicant_role.ilike(like),
                AccessRequest.applicant_department.ilike(like),
                AccessRequest.space_department.ilike(like),
                AccessRequest.departments.ilike(like),
                AccessRequest.nyu_id.ilike(like),
                AccessRequest.n_number.ilike(like),
                AccessRequest.building.ilike(like),
                AccessRequest.room_numbers.ilike(like),
                AccessRequest.access_start_date.ilike(like),
                AccessRequest.access_end_date.ilike(like),
                AccessRequest.access_type.ilike(like),
                AccessRequest.attachment_filename.ilike(like),
            )
        )
    if status:
        query = query.filter(AccessRequest.status == status)

    query = query.order_by(AccessRequest.created_at.desc())
    requests_list = query.all()
    applicant_counts = {
        row[0]: row[1]
        for row in db.session.query(
            AccessRequest.applicant_email, db.func.count(AccessRequest.id)
        ).group_by(AccessRequest.applicant_email)
    }

    return render_template(
        "requests.html",
        requests=requests_list,
        applicant_counts=applicant_counts,
        q=q,
        status=status,
        RequestStatus=RequestStatus,
    )


@app.route("/approver")
def approver_portal():
    """Approver-facing portal for reviewing assigned requests."""
    approver_email = request.args.get("approver_email", "").strip().lower()
    q = request.args.get("q", "").strip()
    status = request.args.get("status", RequestStatus.PENDING.value).strip()

    query = AccessRequest.query
    if approver_email:
        like_email = f"%{approver_email}%"
        query = query.filter(AccessRequest.approver_emails.ilike(like_email))
    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(
                AccessRequest.name.ilike(like),
                AccessRequest.first_name.ilike(like),
                AccessRequest.last_name.ilike(like),
                AccessRequest.applicant_email.ilike(like),
                AccessRequest.applicant_role.ilike(like),
                AccessRequest.applicant_department.ilike(like),
                AccessRequest.space_department.ilike(like),
                AccessRequest.departments.ilike(like),
                AccessRequest.nyu_id.ilike(like),
                AccessRequest.n_number.ilike(like),
                AccessRequest.building.ilike(like),
                AccessRequest.room_numbers.ilike(like),
                AccessRequest.access_start_date.ilike(like),
                AccessRequest.access_end_date.ilike(like),
                AccessRequest.access_type.ilike(like),
                AccessRequest.attachment_filename.ilike(like),
            )
        )
    if status:
        query = query.filter(AccessRequest.status == status)

    query = query.order_by(AccessRequest.created_at.desc())
    requests_list = query.all()
    applicant_counts = {
        row[0]: row[1]
        for row in db.session.query(
            AccessRequest.applicant_email, db.func.count(AccessRequest.id)
        ).group_by(AccessRequest.applicant_email)
    }

    return render_template(
        "approver.html",
        requests=requests_list,
        applicant_counts=applicant_counts,
        approver_email=approver_email,
        q=q,
        status=status,
        RequestStatus=RequestStatus,
    )


ACCESS_ACCOUNTS = {
    # Demo accounts for restricted DB view
    "approver@nyu.edu": "approver",
    "admin@nyu.edu": "admin",
    "viewer@nyu.edu": "viewer",
}


def resolve_access_role(account_email: str) -> str:
    return ACCESS_ACCOUNTS.get(account_email.strip().lower(), "viewer")


@app.route("/db")
def database_view():
    """Database table view for access requests (Excel-like)."""
    account_email = request.args.get("account_email", "").strip().lower()
    role = resolve_access_role(account_email) if account_email else "viewer"
    q = request.args.get("q", "").strip()

    query = AccessRequest.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(
                AccessRequest.name.ilike(like),
                AccessRequest.first_name.ilike(like),
                AccessRequest.last_name.ilike(like),
                AccessRequest.applicant_email.ilike(like),
                AccessRequest.applicant_role.ilike(like),
                AccessRequest.applicant_department.ilike(like),
                AccessRequest.space_department.ilike(like),
                AccessRequest.departments.ilike(like),
                AccessRequest.nyu_id.ilike(like),
                AccessRequest.n_number.ilike(like),
                AccessRequest.building.ilike(like),
                AccessRequest.room_numbers.ilike(like),
                AccessRequest.status.ilike(like),
                AccessRequest.attachment_filename.ilike(like),
            )
        )
    query = query.order_by(AccessRequest.created_at.desc())
    requests_list = query.all()

    if role == "approver" and account_email:
        requests_list = [
            r
            for r in requests_list
            if account_email in [e.lower() for e in r.approver_list()]
        ]

    applicant_counts = {
        row[0]: row[1]
        for row in db.session.query(
            AccessRequest.applicant_email, db.func.count(AccessRequest.id)
        ).group_by(AccessRequest.applicant_email)
    }

    return render_template(
        "db_view.html",
        requests=requests_list,
        account_email=account_email,
        role=role,
        q=q,
        applicant_counts=applicant_counts,
        RequestStatus=RequestStatus,
    )


@app.route("/requests/<int:req_id>/approve", methods=["POST"])
def approve_request(req_id: int):
    """Approve a specific request."""
    req = AccessRequest.query.get_or_404(req_id)
    actor = request.form.get("actor", "").strip()
    approver_email = request.form.get("approver_email", "").strip().lower()
    note = request.form.get("note", "").strip()

    req.status = RequestStatus.APPROVED.value
    req.last_action_by = actor or approver_email or None
    req.last_action_note = note or None
    db.session.commit()

    # Notify PI and requestor
    recipients: List[str] = []
    if req.applicant_email:
        recipients.append(req.applicant_email)
    if req.pi_email:
        recipients.append(req.pi_email)
    recipients.extend(req.approver_list())
    subject = f"[Access Request Approved] {req.name} - {req.building}"
    body = (
        f"The following building access request has been APPROVED.\n\n"
        f"Name: {req.name}\n"
        f"Applicant Email: {req.applicant_email}\n"
        f"Applicant Role: {req.applicant_role or 'N/A'}\n"
        f"Applicant Department: {req.applicant_department or 'N/A'}\n"
        f"Space Department: {req.space_department or req.departments or 'N/A'}\n"
        f"NYU ID: {req.nyu_id}\n"
        f"N#: {req.n_number}\n"
        f"Building: {req.building}\n"
        f"Room(s): {req.room_numbers}\n"
        f"Access Start Date: {req.access_start_date}\n"
        f"Access End Date: {req.access_end_date}\n"
        f"Access Type: {req.access_type}\n"
        f"Attachment: {req.attachment_filename or 'N/A'}\n"
        f"Approved by: {req.last_action_by or 'N/A'}\n"
        f"Note: {req.last_action_note or 'N/A'}\n"
    )
    if recipients:
        send_email(recipients, subject, body)

    if approver_email:
        return redirect(url_for("approver_portal", approver_email=approver_email))
    return redirect(url_for("list_requests"))


@app.route("/requests/<int:req_id>/reject", methods=["POST"])
def reject_request(req_id: int):
    """Reject a specific request."""
    req = AccessRequest.query.get_or_404(req_id)
    actor = request.form.get("actor", "").strip()
    approver_email = request.form.get("approver_email", "").strip().lower()
    note = request.form.get("note", "").strip()

    req.status = RequestStatus.REJECTED.value
    req.last_action_by = actor or approver_email or None
    req.last_action_note = note or None
    db.session.commit()

    recipients: List[str] = []
    if req.applicant_email:
        recipients.append(req.applicant_email)
    if req.pi_email:
        recipients.append(req.pi_email)
    recipients.extend(req.approver_list())
    subject = f"[Access Request Rejected] {req.name} - {req.building}"
    body = (
        f"The following building access request has been REJECTED.\n\n"
        f"Name: {req.name}\n"
        f"Applicant Email: {req.applicant_email}\n"
        f"Applicant Role: {req.applicant_role or 'N/A'}\n"
        f"Applicant Department: {req.applicant_department or 'N/A'}\n"
        f"Space Department: {req.space_department or req.departments or 'N/A'}\n"
        f"NYU ID: {req.nyu_id}\n"
        f"N#: {req.n_number}\n"
        f"Building: {req.building}\n"
        f"Room(s): {req.room_numbers}\n"
        f"Access Start Date: {req.access_start_date}\n"
        f"Access End Date: {req.access_end_date}\n"
        f"Access Type: {req.access_type}\n"
        f"Attachment: {req.attachment_filename or 'N/A'}\n"
        f"Rejected by: {req.last_action_by or 'N/A'}\n"
        f"Note: {req.last_action_note or 'N/A'}\n"
    )
    if recipients:
        send_email(recipients, subject, body)

    if approver_email:
        return redirect(url_for("approver_portal", approver_email=approver_email))
    return redirect(url_for("list_requests"))


@app.route("/requests/<int:req_id>/defer", methods=["POST"])
def defer_request(req_id: int):
    """Defer a specific request for later review."""
    req = AccessRequest.query.get_or_404(req_id)
    actor = request.form.get("actor", "").strip()
    approver_email = request.form.get("approver_email", "").strip().lower()
    note = request.form.get("note", "").strip()

    req.status = RequestStatus.DEFERRED.value
    req.last_action_by = actor or approver_email or None
    req.last_action_note = note or None
    db.session.commit()

    recipients: List[str] = []
    if req.applicant_email:
        recipients.append(req.applicant_email)
    if req.pi_email:
        recipients.append(req.pi_email)
    recipients.extend(req.approver_list())
    subject = f"[Access Request Deferred] {req.name} - {req.building}"
    body = (
        f"The following building access request has been DEFERRED.\n\n"
        f"Name: {req.name}\n"
        f"Applicant Email: {req.applicant_email}\n"
        f"Building: {req.building}\n"
        f"Room(s): {req.room_numbers}\n"
        f"Deferred by: {req.last_action_by or 'N/A'}\n"
        f"Note: {req.last_action_note or 'N/A'}\n"
    )
    if recipients:
        send_email(recipients, subject, body)

    if approver_email:
        return redirect(url_for("approver_portal", approver_email=approver_email))
    return redirect(url_for("list_requests"))


@app.route("/uploads/<path:filename>")
def download_upload(filename: str):
    """Serve uploaded request attachments."""
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename, as_attachment=True)


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        columns = {
            col["name"]
            for col in db.session.execute(db.text("PRAGMA table_info(access_request)")).mappings()
        }
        if "applicant_email" not in columns:
            db.session.execute(
                db.text(
                    "ALTER TABLE access_request ADD COLUMN applicant_email VARCHAR(255) NOT NULL DEFAULT ''"
                )
            )
        if "applicant_role" not in columns:
            db.session.execute(
                db.text("ALTER TABLE access_request ADD COLUMN applicant_role VARCHAR(32)")
            )
        if "applicant_department" not in columns:
            db.session.execute(
                db.text(
                    "ALTER TABLE access_request ADD COLUMN applicant_department VARCHAR(120)"
                )
            )
        if "space_department" not in columns:
            db.session.execute(
                db.text(
                    "ALTER TABLE access_request ADD COLUMN space_department VARCHAR(120)"
                )
            )
        if "departments" not in columns:
            db.session.execute(
                db.text("ALTER TABLE access_request ADD COLUMN departments TEXT")
            )
        if "first_name" not in columns:
            db.session.execute(
                db.text(
                    "ALTER TABLE access_request ADD COLUMN first_name VARCHAR(80) NOT NULL DEFAULT ''"
                )
            )
        if "last_name" not in columns:
            db.session.execute(
                db.text(
                    "ALTER TABLE access_request ADD COLUMN last_name VARCHAR(80) NOT NULL DEFAULT ''"
                )
            )
        if "room_numbers" not in columns:
            db.session.execute(
                db.text(
                    "ALTER TABLE access_request ADD COLUMN room_numbers VARCHAR(255) NOT NULL DEFAULT ''"
                )
            )
        if "access_start_date" not in columns:
            db.session.execute(
                db.text(
                    "ALTER TABLE access_request ADD COLUMN access_start_date VARCHAR(32) NOT NULL DEFAULT ''"
                )
            )
        if "access_end_date" not in columns:
            db.session.execute(
                db.text(
                    "ALTER TABLE access_request ADD COLUMN access_end_date VARCHAR(32) NOT NULL DEFAULT ''"
                )
            )
        if "access_type" not in columns:
            db.session.execute(
                db.text(
                    "ALTER TABLE access_request ADD COLUMN access_type VARCHAR(80) NOT NULL DEFAULT ''"
                )
            )
        if "attachment_filename" not in columns:
            db.session.execute(
                db.text("ALTER TABLE access_request ADD COLUMN attachment_filename VARCHAR(255)")
            )
        db.session.commit()
    app.run(debug=True)

