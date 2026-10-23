CREATE TABLE `evidence` (
	`id` text PRIMARY KEY NOT NULL,
	`name` text NOT NULL,
	`x_handle` text NOT NULL,
	`source_url` text NOT NULL,
	`excerpt` text NOT NULL,
	`status` text NOT NULL,
	`published_at` text,
	`collected_at` text NOT NULL,
	`submitted_by` text NOT NULL
);
