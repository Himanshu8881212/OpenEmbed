-- Worker maintenance: list workspace ids only (no tenant data), so GC can then work inside each tenant's RLS context.
CREATE FUNCTION kb_maintenance_workspaces() RETURNS SETOF uuid
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$ SELECT id FROM workspaces $$;
REVOKE EXECUTE ON FUNCTION kb_maintenance_workspaces FROM PUBLIC, kb_api;
GRANT EXECUTE ON FUNCTION kb_maintenance_workspaces TO kb_worker;
