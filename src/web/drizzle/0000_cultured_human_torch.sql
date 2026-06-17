CREATE TABLE "citations" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"investigation_id" uuid NOT NULL,
	"hypothesis_id" text NOT NULL,
	"stance" text NOT NULL,
	"claim" text NOT NULL,
	"snippet" text NOT NULL,
	"source_path" text NOT NULL,
	"source_line" integer,
	"verified" boolean
);
--> statement-breakpoint
CREATE TABLE "investigations" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	"status" text DEFAULT 'queued' NOT NULL,
	"workspace" text NOT NULL,
	"scenario" text,
	"query" text NOT NULL,
	"provider" text NOT NULL,
	"model" text NOT NULL,
	"max_steps" integer NOT NULL,
	"as_of" timestamp with time zone,
	"window_start" timestamp with time zone,
	"window_end" timestamp with time zone,
	"started_at" timestamp with time zone,
	"finished_at" timestamp with time zone,
	"duration_ms" integer,
	"step_count" integer,
	"outcome" text,
	"summary" text,
	"top_service" text,
	"top_confidence" real,
	"grounding_verified" integer,
	"grounding_total" integer,
	"recommended_action" text,
	"error" text,
	"result_json" jsonb,
	"ledger_json" jsonb
);
--> statement-breakpoint
CREATE TABLE "tool_calls" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"investigation_id" uuid NOT NULL,
	"step" integer NOT NULL,
	"name" text NOT NULL,
	"args" jsonb NOT NULL,
	"result_preview" text DEFAULT '' NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "trace_events" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"investigation_id" uuid NOT NULL,
	"seq" integer NOT NULL,
	"ts" timestamp with time zone NOT NULL,
	"type" text NOT NULL,
	"payload" jsonb NOT NULL
);
--> statement-breakpoint
ALTER TABLE "citations" ADD CONSTRAINT "citations_investigation_id_investigations_id_fk" FOREIGN KEY ("investigation_id") REFERENCES "public"."investigations"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "tool_calls" ADD CONSTRAINT "tool_calls_investigation_id_investigations_id_fk" FOREIGN KEY ("investigation_id") REFERENCES "public"."investigations"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "trace_events" ADD CONSTRAINT "trace_events_investigation_id_investigations_id_fk" FOREIGN KEY ("investigation_id") REFERENCES "public"."investigations"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
CREATE INDEX "citations_investigation_idx" ON "citations" USING btree ("investigation_id");--> statement-breakpoint
CREATE INDEX "investigations_status_created_idx" ON "investigations" USING btree ("status","created_at");--> statement-breakpoint
CREATE INDEX "tool_calls_investigation_step_idx" ON "tool_calls" USING btree ("investigation_id","step");--> statement-breakpoint
CREATE UNIQUE INDEX "trace_events_investigation_seq_idx" ON "trace_events" USING btree ("investigation_id","seq");