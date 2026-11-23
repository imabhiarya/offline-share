CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, description TEXT, applied_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE roles (
	id INTEGER NOT NULL, 
	code VARCHAR(32) NOT NULL, 
	name VARCHAR(64) NOT NULL, 
	description VARCHAR(255) NOT NULL, 
	rank INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (code), 
	UNIQUE (name)
);
CREATE TABLE permissions (
	id INTEGER NOT NULL, 
	code VARCHAR(32) NOT NULL, 
	name VARCHAR(64) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (code)
);
CREATE TABLE sections (
	id INTEGER NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	code VARCHAR(20) NOT NULL, 
	description VARCHAR(255) NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (name)
);
CREATE INDEX ix_sections_created_at ON sections (created_at);
CREATE TABLE users (
	id INTEGER NOT NULL, 
	full_name VARCHAR(120) NOT NULL, 
	login_id VARCHAR(64) NOT NULL, 
	password_hash VARCHAR(255) NOT NULL, 
	section_id INTEGER, 
	assigned_device_id INTEGER, 
	mobile VARCHAR(20) NOT NULL, 
	email VARCHAR(120) NOT NULL, 
	role_id INTEGER NOT NULL, 
	status VARCHAR(16) NOT NULL, 
	is_deleted BOOLEAN NOT NULL, 
	deleted_at DATETIME, 
	failed_logins INTEGER NOT NULL, 
	locked_until DATETIME, 
	must_change_password BOOLEAN NOT NULL, 
	password_changed_at DATETIME, 
	last_login_at DATETIME, 
	updated_at DATETIME NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(section_id) REFERENCES sections (id) ON DELETE SET NULL, 
	FOREIGN KEY(assigned_device_id) REFERENCES devices (id) ON DELETE SET NULL, 
	FOREIGN KEY(role_id) REFERENCES roles (id)
);
CREATE INDEX ix_users_role_id ON users (role_id);
CREATE INDEX ix_users_status ON users (status);
CREATE INDEX ix_users_created_at ON users (created_at);
CREATE INDEX ix_users_section_id ON users (section_id);
CREATE INDEX ix_users_is_deleted ON users (is_deleted);
CREATE UNIQUE INDEX ix_users_login_id ON users (login_id);
CREATE INDEX ix_users_assigned_device_id ON users (assigned_device_id);
CREATE TABLE devices (
	id INTEGER NOT NULL, 
	uid VARCHAR(32) NOT NULL, 
	pc_name VARCHAR(64) NOT NULL, 
	ip_address VARCHAR(45) NOT NULL, 
	mac_address VARCHAR(32) NOT NULL, 
	section_id INTEGER, 
	connection_type VARCHAR(16) NOT NULL, 
	status VARCHAR(16) NOT NULL, 
	is_unknown BOOLEAN NOT NULL, 
	os_info VARCHAR(120) NOT NULL, 
	notes VARCHAR(255) NOT NULL, 
	agent_token_hash VARCHAR(128) NOT NULL, 
	agent_version VARCHAR(32) NOT NULL, 
	last_seen_at DATETIME, 
	last_browser_at DATETIME, 
	last_agent_at DATETIME, 
	last_user_id INTEGER, 
	approved_at DATETIME, 
	approved_by INTEGER, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (uid), 
	FOREIGN KEY(section_id) REFERENCES sections (id) ON DELETE SET NULL, 
	FOREIGN KEY(last_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(approved_by) REFERENCES users (id) ON DELETE SET NULL
);
CREATE INDEX ix_devices_pc_name ON devices (pc_name);
CREATE INDEX ix_devices_created_at ON devices (created_at);
CREATE INDEX ix_devices_ip_address ON devices (ip_address);
CREATE INDEX ix_devices_status ON devices (status);
CREATE INDEX ix_devices_section_id ON devices (section_id);
CREATE TABLE role_permissions (
	role_id INTEGER NOT NULL, 
	permission_id INTEGER NOT NULL, 
	PRIMARY KEY (role_id, permission_id), 
	FOREIGN KEY(role_id) REFERENCES roles (id) ON DELETE CASCADE, 
	FOREIGN KEY(permission_id) REFERENCES permissions (id) ON DELETE CASCADE
);
CREATE TABLE user_permissions (
	user_id INTEGER NOT NULL, 
	permission_id INTEGER NOT NULL, 
	granted BOOLEAN NOT NULL, 
	PRIMARY KEY (user_id, permission_id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(permission_id) REFERENCES permissions (id) ON DELETE CASCADE
);
CREATE TABLE sessions (
	id VARCHAR(128) NOT NULL, 
	user_id INTEGER NOT NULL, 
	device_id INTEGER, 
	ip_address VARCHAR(45) NOT NULL, 
	user_agent VARCHAR(255) NOT NULL, 
	csrf_token VARCHAR(64) NOT NULL, 
	last_seen_at DATETIME NOT NULL, 
	expires_at DATETIME NOT NULL, 
	revoked_at DATETIME, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(device_id) REFERENCES devices (id) ON DELETE SET NULL
);
CREATE INDEX ix_sessions_created_at ON sessions (created_at);
CREATE INDEX ix_sessions_user_id ON sessions (user_id);
CREATE TABLE transfers (
	id INTEGER NOT NULL, 
	transfer_uid VARCHAR(32) NOT NULL, 
	sender_user_id INTEGER, 
	sender_device_id INTEGER, 
	sender_name VARCHAR(120) NOT NULL, 
	sender_login VARCHAR(64) NOT NULL, 
	sender_pc VARCHAR(64) NOT NULL, 
	sender_ip VARCHAR(45) NOT NULL, 
	subject VARCHAR(255) NOT NULL, 
	kind VARCHAR(8) NOT NULL, 
	priority VARCHAR(8) NOT NULL, 
	notify BOOLEAN NOT NULL, 
	delivery_confirmation BOOLEAN NOT NULL, 
	read_receipt BOOLEAN NOT NULL, 
	expires_at DATETIME, 
	total_size BIGINT NOT NULL, 
	file_count INTEGER NOT NULL, 
	reply_to_id INTEGER, 
	forwarded_from_id INTEGER, 
	sender_deleted BOOLEAN NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(sender_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(sender_device_id) REFERENCES devices (id) ON DELETE SET NULL, 
	FOREIGN KEY(reply_to_id) REFERENCES transfers (id) ON DELETE SET NULL, 
	FOREIGN KEY(forwarded_from_id) REFERENCES transfers (id) ON DELETE SET NULL
);
CREATE UNIQUE INDEX ix_transfers_transfer_uid ON transfers (transfer_uid);
CREATE INDEX ix_transfers_created_at ON transfers (created_at);
CREATE INDEX ix_transfers_sender_user_id ON transfers (sender_user_id);
CREATE TABLE drafts (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	subject VARCHAR(255) NOT NULL, 
	body_html TEXT NOT NULL, 
	recipient_ids TEXT NOT NULL, 
	attachment_ids TEXT NOT NULL, 
	options TEXT NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);
CREATE INDEX ix_drafts_user_id ON drafts (user_id);
CREATE INDEX ix_drafts_created_at ON drafts (created_at);
CREATE TABLE notifications (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	type VARCHAR(32) NOT NULL, 
	title VARCHAR(200) NOT NULL, 
	body VARCHAR(500) NOT NULL, 
	link VARCHAR(200) NOT NULL, 
	is_read BOOLEAN NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);
CREATE INDEX ix_notifications_user_id ON notifications (user_id);
CREATE INDEX ix_notifications_is_read ON notifications (is_read);
CREATE INDEX ix_notifications_created_at ON notifications (created_at);
CREATE TABLE folders (
	id INTEGER NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	parent_id INTEGER, 
	section_id INTEGER, 
	is_system BOOLEAN NOT NULL, 
	system_key VARCHAR(32) NOT NULL, 
	created_by INTEGER, 
	deleted_at DATETIME, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_folder_name UNIQUE (parent_id, name), 
	FOREIGN KEY(parent_id) REFERENCES folders (id) ON DELETE CASCADE, 
	FOREIGN KEY(section_id) REFERENCES sections (id) ON DELETE SET NULL, 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);
CREATE INDEX ix_folders_parent_id ON folders (parent_id);
CREATE INDEX ix_folders_created_at ON folders (created_at);
CREATE TABLE audit_logs (
	id INTEGER NOT NULL, 
	user_id INTEGER, 
	user_name VARCHAR(120) NOT NULL, 
	ip_address VARCHAR(45) NOT NULL, 
	action VARCHAR(64) NOT NULL, 
	entity_type VARCHAR(32) NOT NULL, 
	entity_id VARCHAR(64) NOT NULL, 
	details TEXT NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL
);
CREATE INDEX ix_audit_logs_user_id ON audit_logs (user_id);
CREATE INDEX ix_audit_entity ON audit_logs (entity_type, entity_id);
CREATE INDEX ix_audit_logs_created_at ON audit_logs (created_at);
CREATE INDEX ix_audit_logs_action ON audit_logs (action);
CREATE TABLE application_settings (
	"key" VARCHAR(64) NOT NULL, 
	value TEXT NOT NULL, 
	updated_at DATETIME NOT NULL, 
	updated_by INTEGER, 
	PRIMARY KEY ("key"), 
	FOREIGN KEY(updated_by) REFERENCES users (id) ON DELETE SET NULL
);
CREATE TABLE backup_history (
	id INTEGER NOT NULL, 
	filename VARCHAR(255) NOT NULL, 
	path VARCHAR(500) NOT NULL, 
	size BIGINT NOT NULL, 
	kind VARCHAR(16) NOT NULL, 
	includes_files BOOLEAN NOT NULL, 
	status VARCHAR(16) NOT NULL, 
	message VARCHAR(500) NOT NULL, 
	created_by INTEGER, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);
CREATE INDEX ix_backup_history_created_at ON backup_history (created_at);
CREATE TABLE messages (
	id INTEGER NOT NULL, 
	transfer_id INTEGER NOT NULL, 
	body_html TEXT NOT NULL, 
	body_text TEXT NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (transfer_id), 
	FOREIGN KEY(transfer_id) REFERENCES transfers (id) ON DELETE CASCADE
);
CREATE TABLE attachments (
	id INTEGER NOT NULL, 
	uid VARCHAR(32) NOT NULL, 
	transfer_id INTEGER, 
	uploader_id INTEGER, 
	original_name VARCHAR(255) NOT NULL, 
	stored_path VARCHAR(400) NOT NULL, 
	extension VARCHAR(16) NOT NULL, 
	mime_type VARCHAR(120) NOT NULL, 
	size BIGINT NOT NULL, 
	sha256 VARCHAR(64) NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (uid), 
	FOREIGN KEY(transfer_id) REFERENCES transfers (id) ON DELETE CASCADE, 
	FOREIGN KEY(uploader_id) REFERENCES users (id) ON DELETE SET NULL
);
CREATE INDEX ix_attachments_created_at ON attachments (created_at);
CREATE INDEX ix_attachments_transfer_id ON attachments (transfer_id);
CREATE INDEX ix_attachments_uploader_id ON attachments (uploader_id);
CREATE TABLE transfer_recipients (
	id INTEGER NOT NULL, 
	transfer_id INTEGER NOT NULL, 
	recipient_user_id INTEGER, 
	recipient_device_id INTEGER, 
	recipient_name VARCHAR(120) NOT NULL, 
	recipient_login VARCHAR(64) NOT NULL, 
	recipient_pc VARCHAR(64) NOT NULL, 
	recipient_ip VARCHAR(45) NOT NULL, 
	status VARCHAR(12) NOT NULL, 
	attempts INTEGER NOT NULL, 
	last_attempt_at DATETIME, 
	sent_at DATETIME, 
	delivered_at DATETIME, 
	read_at DATETIME, 
	failed_at DATETIME, 
	failed_reason VARCHAR(255) NOT NULL, 
	delivered_ip VARCHAR(45) NOT NULL, 
	is_flagged BOOLEAN NOT NULL, 
	is_important BOOLEAN NOT NULL, 
	is_archived BOOLEAN NOT NULL, 
	is_deleted BOOLEAN NOT NULL, 
	deleted_at DATETIME, 
	purged BOOLEAN NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_transfer_recipient UNIQUE (transfer_id, recipient_user_id), 
	FOREIGN KEY(transfer_id) REFERENCES transfers (id) ON DELETE CASCADE, 
	FOREIGN KEY(recipient_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(recipient_device_id) REFERENCES devices (id) ON DELETE SET NULL
);
CREATE INDEX ix_transfer_recipients_transfer_id ON transfer_recipients (transfer_id);
CREATE INDEX ix_tr_user_status ON transfer_recipients (recipient_user_id, status);
CREATE INDEX ix_transfer_recipients_recipient_user_id ON transfer_recipients (recipient_user_id);
CREATE INDEX ix_transfer_recipients_status ON transfer_recipients (status);
CREATE INDEX ix_transfer_recipients_created_at ON transfer_recipients (created_at);
CREATE TABLE file_repository (
	id INTEGER NOT NULL, 
	uid VARCHAR(32) NOT NULL, 
	folder_id INTEGER NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	extension VARCHAR(16) NOT NULL, 
	mime_type VARCHAR(120) NOT NULL, 
	size BIGINT NOT NULL, 
	sha256 VARCHAR(64) NOT NULL, 
	stored_path VARCHAR(400) NOT NULL, 
	current_version INTEGER NOT NULL, 
	description VARCHAR(500) NOT NULL, 
	access_scope VARCHAR(16) NOT NULL, 
	section_id INTEGER, 
	uploaded_by INTEGER, 
	uploaded_by_name VARCHAR(120) NOT NULL, 
	updated_at DATETIME NOT NULL, 
	deleted_at DATETIME, 
	deleted_by INTEGER, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (uid), 
	FOREIGN KEY(folder_id) REFERENCES folders (id), 
	FOREIGN KEY(section_id) REFERENCES sections (id) ON DELETE SET NULL, 
	FOREIGN KEY(uploaded_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(deleted_by) REFERENCES users (id) ON DELETE SET NULL
);
CREATE INDEX ix_file_repository_sha256 ON file_repository (sha256);
CREATE INDEX ix_file_repository_uploaded_by ON file_repository (uploaded_by);
CREATE INDEX ix_file_repository_name ON file_repository (name);
CREATE INDEX ix_file_repository_deleted_at ON file_repository (deleted_at);
CREATE INDEX ix_file_repository_created_at ON file_repository (created_at);
CREATE INDEX ix_file_repository_folder_id ON file_repository (folder_id);
CREATE TABLE file_permissions (
	id INTEGER NOT NULL, 
	file_id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_file_user UNIQUE (file_id, user_id), 
	FOREIGN KEY(file_id) REFERENCES file_repository (id) ON DELETE CASCADE, 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);
CREATE INDEX ix_file_permissions_user_id ON file_permissions (user_id);
CREATE INDEX ix_file_permissions_file_id ON file_permissions (file_id);
CREATE TABLE file_versions (
	id INTEGER NOT NULL, 
	file_id INTEGER NOT NULL, 
	version INTEGER NOT NULL, 
	stored_path VARCHAR(400) NOT NULL, 
	size BIGINT NOT NULL, 
	sha256 VARCHAR(64) NOT NULL, 
	uploaded_by INTEGER, 
	uploaded_by_name VARCHAR(120) NOT NULL, 
	note VARCHAR(255) NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_file_version UNIQUE (file_id, version), 
	FOREIGN KEY(file_id) REFERENCES file_repository (id) ON DELETE CASCADE, 
	FOREIGN KEY(uploaded_by) REFERENCES users (id) ON DELETE SET NULL
);
CREATE INDEX ix_file_versions_created_at ON file_versions (created_at);
CREATE INDEX ix_file_versions_file_id ON file_versions (file_id);
CREATE VIRTUAL TABLE search_messages USING fts5(transfer_id UNINDEXED, transfer_uid, subject, body, filenames, sender, tokenize='unicode61')
/* search_messages(transfer_id,transfer_uid,subject,body,filenames,sender) */;
CREATE VIRTUAL TABLE search_files USING fts5(file_id UNINDEXED, name, description, uploader, tokenize='unicode61')
/* search_files(file_id,name,description,uploader) */;
CREATE INDEX ix_tr_status_attempt ON transfer_recipients(status, last_attempt_at);
CREATE INDEX ix_transfers_sender_created ON transfers(sender_user_id, created_at);
CREATE INDEX ix_notifications_user_read ON notifications(user_id, is_read);
