CREATE TABLE background_jobs (
	id VARCHAR(36) NOT NULL, 
	task_name VARCHAR(100) NOT NULL, 
	payload TEXT NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	attempts INTEGER NOT NULL, 
	max_attempts INTEGER NOT NULL, 
	error_message TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	started_at TIMESTAMP WITHOUT TIME ZONE, 
	completed_at TIMESTAMP WITHOUT TIME ZONE, 
	CONSTRAINT pk_background_jobs PRIMARY KEY (id)
);

CREATE TABLE categories (
	id VARCHAR(36) NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	slug VARCHAR(100) NOT NULL, 
	description VARCHAR(500), 
	icon VARCHAR(50), 
	sort_order INTEGER, 
	CONSTRAINT pk_categories PRIMARY KEY (id), 
	CONSTRAINT uq_categories_slug UNIQUE (slug)
);

CREATE TABLE system_settings (
	id VARCHAR(36) NOT NULL, 
	key VARCHAR(100) NOT NULL, 
	value TEXT, 
	description VARCHAR(255), 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	CONSTRAINT pk_system_settings PRIMARY KEY (id), 
	CONSTRAINT uq_system_settings_key UNIQUE (key)
);

CREATE TABLE users (
	id VARCHAR(36) NOT NULL, 
	email VARCHAR(255) NOT NULL, 
	password_hash VARCHAR(255) NOT NULL, 
	phone VARCHAR(20), 
	is_active BOOLEAN NOT NULL, 
	role VARCHAR(20) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	last_login TIMESTAMP WITHOUT TIME ZONE, 
	login_count INTEGER NOT NULL, 
	reset_token VARCHAR(100), 
	reset_token_expiry TIMESTAMP WITHOUT TIME ZONE, 
	must_change_password BOOLEAN NOT NULL, 
	created_by VARCHAR(36), 
	temp_password_hash VARCHAR(255), 
	CONSTRAINT pk_users PRIMARY KEY (id), 
	CONSTRAINT uq_users_email UNIQUE (email), 
	CONSTRAINT uq_users_reset_token UNIQUE (reset_token), 
	CONSTRAINT fk_users_created_by_users FOREIGN KEY(created_by) REFERENCES users (id)
);

CREATE TABLE audit_logs (
	id VARCHAR(36) NOT NULL, 
	actor_id VARCHAR(36), 
	action VARCHAR(100) NOT NULL, 
	target_type VARCHAR(50), 
	target_id VARCHAR(36), 
	detail TEXT, 
	ip_address VARCHAR(45), 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	CONSTRAINT pk_audit_logs PRIMARY KEY (id), 
	CONSTRAINT fk_audit_logs_actor_id_users FOREIGN KEY(actor_id) REFERENCES users (id)
);

CREATE TABLE content_reports (
	id VARCHAR(36) NOT NULL, 
	reporter_id VARCHAR(36) NOT NULL, 
	target_type VARCHAR(20) NOT NULL, 
	target_id VARCHAR(36) NOT NULL, 
	reason VARCHAR(255) NOT NULL, 
	detail TEXT, 
	status VARCHAR(20) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	resolved_at TIMESTAMP WITHOUT TIME ZONE, 
	resolved_by VARCHAR(36), 
	action_taken VARCHAR(50), 
	CONSTRAINT pk_content_reports PRIMARY KEY (id), 
	CONSTRAINT fk_content_reports_reporter_id_users FOREIGN KEY(reporter_id) REFERENCES users (id) ON DELETE CASCADE, 
	CONSTRAINT fk_content_reports_resolved_by_users FOREIGN KEY(resolved_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE TABLE courses (
	id VARCHAR(36) NOT NULL, 
	title VARCHAR(255) NOT NULL, 
	short_description VARCHAR(500) NOT NULL, 
	description TEXT NOT NULL, 
	cover_image_url VARCHAR(500) NOT NULL, 
	total_lessons INTEGER NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	is_deleted BOOLEAN NOT NULL, 
	category_id VARCHAR(36), 
	teacher_id VARCHAR(36) NOT NULL, 
	rejection_note TEXT, 
	submitted_at TIMESTAMP WITHOUT TIME ZONE, 
	published_at TIMESTAMP WITHOUT TIME ZONE, 
	price INTEGER NOT NULL, 
	tags VARCHAR(500) NOT NULL, 
	level VARCHAR(20) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	reviewed_by VARCHAR(36), 
	reviewed_at TIMESTAMP WITHOUT TIME ZONE, 
	review_note TEXT, 
	starts_at TIMESTAMP WITHOUT TIME ZONE, 
	ends_at TIMESTAMP WITHOUT TIME ZONE, 
	enrollment_deadline TIMESTAMP WITHOUT TIME ZONE, 
	max_students INTEGER, 
	CONSTRAINT pk_courses PRIMARY KEY (id), 
	CONSTRAINT fk_courses_category_id_categories FOREIGN KEY(category_id) REFERENCES categories (id), 
	CONSTRAINT fk_courses_teacher_id_users FOREIGN KEY(teacher_id) REFERENCES users (id), 
	CONSTRAINT fk_courses_reviewed_by_users FOREIGN KEY(reviewed_by) REFERENCES users (id)
);

CREATE TABLE notifications (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	type VARCHAR(50) NOT NULL, 
	message VARCHAR(500) NOT NULL, 
	link VARCHAR(500), 
	is_read BOOLEAN, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	CONSTRAINT pk_notifications PRIMARY KEY (id), 
	CONSTRAINT fk_notifications_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE announcements (
	id VARCHAR(36) NOT NULL, 
	course_id VARCHAR(36) NOT NULL, 
	author_id VARCHAR(36) NOT NULL, 
	title VARCHAR(255) NOT NULL, 
	body TEXT NOT NULL, 
	is_pinned BOOLEAN, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	CONSTRAINT pk_announcements PRIMARY KEY (id), 
	CONSTRAINT fk_announcements_course_id_courses FOREIGN KEY(course_id) REFERENCES courses (id) ON DELETE CASCADE, 
	CONSTRAINT fk_announcements_author_id_users FOREIGN KEY(author_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE assignments (
	id VARCHAR(36) NOT NULL, 
	course_id VARCHAR(36) NOT NULL, 
	title VARCHAR(255) NOT NULL, 
	description TEXT NOT NULL, 
	deadline TIMESTAMP WITHOUT TIME ZONE, 
	allow_file BOOLEAN, 
	allow_text BOOLEAN, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	CONSTRAINT pk_assignments PRIMARY KEY (id), 
	CONSTRAINT fk_assignments_course_id_courses FOREIGN KEY(course_id) REFERENCES courses (id) ON DELETE CASCADE
);

CREATE TABLE certificates (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	course_id VARCHAR(36) NOT NULL, 
	cert_code VARCHAR(100), 
	issued_at TIMESTAMP WITHOUT TIME ZONE, 
	CONSTRAINT pk_certificates PRIMARY KEY (id), 
	CONSTRAINT uq_certificates_user_course UNIQUE (user_id, course_id), 
	CONSTRAINT fk_certificates_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	CONSTRAINT fk_certificates_course_id_courses FOREIGN KEY(course_id) REFERENCES courses (id) ON DELETE CASCADE, 
	CONSTRAINT uq_certificates_cert_code UNIQUE (cert_code)
);

CREATE TABLE enrollments (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	course_id VARCHAR(36) NOT NULL, 
	enrolled_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	CONSTRAINT pk_enrollments PRIMARY KEY (id), 
	CONSTRAINT uq_enrollments_user_course UNIQUE (user_id, course_id), 
	CONSTRAINT fk_enrollments_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	CONSTRAINT fk_enrollments_course_id_courses FOREIGN KEY(course_id) REFERENCES courses (id) ON DELETE CASCADE
);

CREATE TABLE forum_threads (
	id VARCHAR(36) NOT NULL, 
	course_id VARCHAR(36) NOT NULL, 
	author_id VARCHAR(36) NOT NULL, 
	title VARCHAR(255) NOT NULL, 
	body TEXT NOT NULL, 
	is_pinned BOOLEAN, 
	is_hidden BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	CONSTRAINT pk_forum_threads PRIMARY KEY (id), 
	CONSTRAINT fk_forum_threads_course_id_courses FOREIGN KEY(course_id) REFERENCES courses (id) ON DELETE CASCADE, 
	CONSTRAINT fk_forum_threads_author_id_users FOREIGN KEY(author_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE lessons (
	id VARCHAR(36) NOT NULL, 
	course_id VARCHAR(36) NOT NULL, 
	title VARCHAR(255) NOT NULL, 
	video_url VARCHAR(500) NOT NULL, 
	document_url VARCHAR(500) NOT NULL, 
	sequence_order INTEGER NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	CONSTRAINT pk_lessons PRIMARY KEY (id), 
	CONSTRAINT fk_lessons_course_id_courses FOREIGN KEY(course_id) REFERENCES courses (id) ON DELETE CASCADE
);

CREATE TABLE quizzes (
	id VARCHAR(36) NOT NULL, 
	course_id VARCHAR(36) NOT NULL, 
	title VARCHAR(255) NOT NULL, 
	pass_score INTEGER, 
	max_attempts INTEGER, 
	time_limit INTEGER, 
	random_question_count INTEGER, 
	due_date TIMESTAMP WITHOUT TIME ZONE, 
	is_published BOOLEAN, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	CONSTRAINT pk_quizzes PRIMARY KEY (id), 
	CONSTRAINT fk_quizzes_course_id_courses FOREIGN KEY(course_id) REFERENCES courses (id) ON DELETE CASCADE
);

CREATE TABLE forum_replies (
	id VARCHAR(36) NOT NULL, 
	thread_id VARCHAR(36) NOT NULL, 
	author_id VARCHAR(36) NOT NULL, 
	body TEXT NOT NULL, 
	is_hidden BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	CONSTRAINT pk_forum_replies PRIMARY KEY (id), 
	CONSTRAINT fk_forum_replies_thread_id_forum_threads FOREIGN KEY(thread_id) REFERENCES forum_threads (id) ON DELETE CASCADE, 
	CONSTRAINT fk_forum_replies_author_id_users FOREIGN KEY(author_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE learning_logs (
	log_id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	lesson_id VARCHAR(36) NOT NULL, 
	action_type VARCHAR(20) NOT NULL, 
	timestamp TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	CONSTRAINT pk_learning_logs PRIMARY KEY (log_id), 
	CONSTRAINT fk_learning_logs_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	CONSTRAINT fk_learning_logs_lesson_id_lessons FOREIGN KEY(lesson_id) REFERENCES lessons (id) ON DELETE CASCADE
);

CREATE TABLE questions (
	id VARCHAR(36) NOT NULL, 
	quiz_id VARCHAR(36) NOT NULL, 
	text TEXT NOT NULL, 
	q_type VARCHAR(20), 
	sequence_order INTEGER, 
	CONSTRAINT pk_questions PRIMARY KEY (id), 
	CONSTRAINT fk_questions_quiz_id_quizzes FOREIGN KEY(quiz_id) REFERENCES quizzes (id) ON DELETE CASCADE
);

CREATE TABLE quiz_attempts (
	id VARCHAR(36) NOT NULL, 
	quiz_id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	score INTEGER, 
	passed BOOLEAN, 
	attempted_at TIMESTAMP WITHOUT TIME ZONE, 
	completed_at TIMESTAMP WITHOUT TIME ZONE, 
	CONSTRAINT pk_quiz_attempts PRIMARY KEY (id), 
	CONSTRAINT fk_quiz_attempts_quiz_id_quizzes FOREIGN KEY(quiz_id) REFERENCES quizzes (id) ON DELETE CASCADE, 
	CONSTRAINT fk_quiz_attempts_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE submissions (
	id VARCHAR(36) NOT NULL, 
	assignment_id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	text_content TEXT, 
	file_path VARCHAR(500), 
	submitted_at TIMESTAMP WITHOUT TIME ZONE, 
	status VARCHAR(20), 
	score INTEGER, 
	feedback TEXT, 
	graded_at TIMESTAMP WITHOUT TIME ZONE, 
	graded_by VARCHAR(36), 
	CONSTRAINT pk_submissions PRIMARY KEY (id), 
	CONSTRAINT uq_submissions_user_assignment UNIQUE (user_id, assignment_id), 
	CONSTRAINT fk_submissions_assignment_id_assignments FOREIGN KEY(assignment_id) REFERENCES assignments (id) ON DELETE CASCADE, 
	CONSTRAINT fk_submissions_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	CONSTRAINT fk_submissions_graded_by_users FOREIGN KEY(graded_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE TABLE choices (
	id VARCHAR(36) NOT NULL, 
	question_id VARCHAR(36) NOT NULL, 
	text TEXT NOT NULL, 
	is_correct BOOLEAN, 
	CONSTRAINT pk_choices PRIMARY KEY (id), 
	CONSTRAINT fk_choices_question_id_questions FOREIGN KEY(question_id) REFERENCES questions (id) ON DELETE CASCADE
);

CREATE TABLE quiz_answers (
	id VARCHAR(36) NOT NULL, 
	attempt_id VARCHAR(36) NOT NULL, 
	question_id VARCHAR(36) NOT NULL, 
	choice_id VARCHAR(36), 
	text_answer TEXT, 
	CONSTRAINT pk_quiz_answers PRIMARY KEY (id), 
	CONSTRAINT fk_quiz_answers_attempt_id_quiz_attempts FOREIGN KEY(attempt_id) REFERENCES quiz_attempts (id) ON DELETE CASCADE, 
	CONSTRAINT fk_quiz_answers_question_id_questions FOREIGN KEY(question_id) REFERENCES questions (id) ON DELETE CASCADE, 
	CONSTRAINT fk_quiz_answers_choice_id_choices FOREIGN KEY(choice_id) REFERENCES choices (id) ON DELETE CASCADE
);