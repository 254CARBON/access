-- Initialize database for 254Carbon Access Layer

-- Create database if not exists
CREATE DATABASE IF NOT EXISTS access_layer;

-- Use the database
\c access_layer;

-- Create entitlements tables
CREATE TABLE IF NOT EXISTS entitlement_rules (
    id SERIAL PRIMARY KEY,
    rule_id VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    conditions JSONB NOT NULL,
    action VARCHAR(50) NOT NULL,
    priority INTEGER DEFAULT 0,
    resource VARCHAR(255),
    tenant_id VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NULL,
    is_active BOOLEAN DEFAULT TRUE
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_entitlement_rules_rule_id ON entitlement_rules(rule_id);
CREATE INDEX IF NOT EXISTS idx_entitlement_rules_tenant_id ON entitlement_rules(tenant_id);
CREATE INDEX IF NOT EXISTS idx_entitlement_rules_resource ON entitlement_rules(resource);
CREATE INDEX IF NOT EXISTS idx_entitlement_rules_active ON entitlement_rules(is_active);

-- Create audit table for rule changes
CREATE TABLE IF NOT EXISTS entitlement_rule_audit (
    id SERIAL PRIMARY KEY,
    rule_id VARCHAR(255) NOT NULL,
    action VARCHAR(50) NOT NULL, -- CREATE, UPDATE, DELETE
    old_values JSONB,
    new_values JSONB,
    changed_by VARCHAR(255),
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index for audit table
CREATE INDEX IF NOT EXISTS idx_entitlement_rule_audit_rule_id ON entitlement_rule_audit(rule_id);
CREATE INDEX IF NOT EXISTS idx_entitlement_rule_audit_changed_at ON entitlement_rule_audit(changed_at);

-- Insert default rules
INSERT INTO entitlement_rules (rule_id, name, description, conditions, action, priority, resource, tenant_id) VALUES
(
    'default-admin',
    'Admin Full Access',
    'Full access for admin users',
    '[{"field": "user_roles", "operator": "contains", "value": "admin"}]',
    'allow',
    100,
    '*',
    '*'
),
(
    'default-tenant-isolation',
    'Tenant Isolation',
    'Users can only access their tenant data',
    '[{"field": "tenant_id", "operator": "equals", "value": "{{user_tenant_id}}"}]',
    'allow',
    50,
    '*',
    '*'
),
(
    'default-read-only',
    'Read Only Access',
    'Read-only access for regular users',
    '[{"field": "action", "operator": "equals", "value": "read"}, {"field": "user_roles", "operator": "contains", "value": "user"}]',
    'allow',
    10,
    '*',
    '*'
)
ON CONFLICT (rule_id) DO NOTHING;

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger for updated_at
CREATE TRIGGER update_entitlement_rules_updated_at 
    BEFORE UPDATE ON entitlement_rules 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE access_layer TO access_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO access_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO access_user;
