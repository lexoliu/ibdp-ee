-- Warning: This script is designed for single-threaded use only.

counter = 0

-- FNV-1a 32-bit hash
function fnv1a_hash(x)
  local hash = 2166136261
  local prime = 16777619
  local s = tostring(x)
  for i = 1, #s do
    hash = hash ~ string.byte(s, i)
    hash = (hash * prime) % 2^32
  end
  return tostring(hash)
end

function request()
  counter = counter + 1
  local key = fnv1a_hash(counter)
  local value = "val" .. key

  return wrk.format("POST", "/kv/" .. key,
    {["Content-Type"]="text/plain"},
    value)
end


