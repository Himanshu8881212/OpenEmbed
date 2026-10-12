-- Deleting a source must not be blocked by the upload record that once replaced it (found by composition tests).
ALTER TABLE upload_files DROP CONSTRAINT upload_files_replaces_file_id_fkey,
  ADD CONSTRAINT upload_files_replaces_file_id_fkey FOREIGN KEY (replaces_file_id) REFERENCES files ON DELETE SET NULL;
