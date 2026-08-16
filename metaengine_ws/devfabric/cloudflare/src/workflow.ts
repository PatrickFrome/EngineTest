import { WorkflowEntrypoint, type WorkflowEvent, type WorkflowStep } from 'cloudflare:workers';
import { buildWorkflowPlan, type WorkflowInput } from './workflow_core.ts';

export class MetaengineEdgeWorkflow extends WorkflowEntrypoint<Env, WorkflowInput> {
  async run(event: WorkflowEvent<WorkflowInput>, step: WorkflowStep) {
    const plan = buildWorkflowPlan(event.payload);
    if (plan.status !== 'READY') return { status: 'QUOTA_EXHAUSTED' };
    for (const item of plan.steps) {
      await step.do(item.name, async () => ({ ref: item.ref, stored_body: false }));
    }
    return { status: 'COMPLETE', refs: plan.steps.map((item) => item.ref) };
  }
}
