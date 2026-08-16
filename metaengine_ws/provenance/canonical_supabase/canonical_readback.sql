select checkpoint_id, payload_root_sha256, active_policy_hash, verification_status, is_current
from destruktion_meta.chat_capsule_checkpoint
where is_current is true
order by created_at desc
limit 1;

select pointer_id, policy_hash, generation, promotion_receipt_hash
from destruktion_meta.champion_pointer
order by pointer_id;
