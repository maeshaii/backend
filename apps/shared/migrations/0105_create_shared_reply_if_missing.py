from django.db import migrations


class Migration(migrations.Migration):

	dependencies = [
		('shared', '0103_merge_20251021_2330'),
	]

	operations = [
		migrations.RunSQL(
			# Create table only if it does not exist (PostgreSQL)
			"""
			CREATE TABLE IF NOT EXISTS shared_reply (
			    reply_id SERIAL PRIMARY KEY,
			    user_id INTEGER NOT NULL REFERENCES shared_user (user_id) DEFERRABLE INITIALLY DEFERRED,
			    comment_id INTEGER NOT NULL REFERENCES shared_comment (comment_id) DEFERRABLE INITIALLY DEFERRED,
			    reply_content TEXT NOT NULL DEFAULT '',
			    date_created TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
			);

			-- Create indexes if they don't already exist
			CREATE INDEX IF NOT EXISTS shared_repl_comment_657ed9_idx ON shared_reply (comment_id, date_created);
			CREATE INDEX IF NOT EXISTS shared_repl_user_id_240ea8_idx ON shared_reply (user_id, date_created);
			""",
			# Reverse SQL: drop the table if it exists (safe rollback)
			"""
			DROP TABLE IF EXISTS shared_reply CASCADE;
			""",
		),
	]


