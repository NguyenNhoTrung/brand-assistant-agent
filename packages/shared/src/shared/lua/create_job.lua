-- Idempotency + tạo job + đẩy queue trong một bước nguyên tử.
-- KEYS: 1 idem:{uid}:{key}  2 job:{id}  3 user:{uid}:jobs  4 queue:jobs  5 conv:{cid}  6 user:{uid}:convs
-- ARGV: 1 job_id  2 uid  3 cid  4 input_json  5 now_ms  6 job_type  7 title
-- cid rỗng (job ingest) → không gắn conversation, KEYS 5–6 bỏ qua
local existing = redis.call('GET', KEYS[1])
if existing then return {0, existing} end

redis.call('HSET', KEYS[2], 'user_id', ARGV[2], 'conversation_id', ARGV[3], 'type', ARGV[6],
           'status', 'queued', 'input', ARGV[4], 'created_at', ARGV[5])
redis.call('EXPIRE', KEYS[2], 604800)
redis.call('ZADD', KEYS[3], ARGV[5], ARGV[1])
redis.call('EXPIRE', KEYS[3], 604800)
if ARGV[3] ~= '' then
  if redis.call('EXISTS', KEYS[5]) == 0 then
    redis.call('HSET', KEYS[5], 'user_id', ARGV[2], 'title', ARGV[7])
  end
  redis.call('HSET', KEYS[5], 'updated_at', ARGV[5], 'active_job_id', ARGV[1])
  redis.call('EXPIRE', KEYS[5], 2592000)
  redis.call('ZADD', KEYS[6], ARGV[5], ARGV[3])
  redis.call('EXPIRE', KEYS[6], 2592000)
end
redis.call('LPUSH', KEYS[4], ARGV[1])
redis.call('SET', KEYS[1], ARGV[1], 'EX', 86400)
return {1, ARGV[1]}
