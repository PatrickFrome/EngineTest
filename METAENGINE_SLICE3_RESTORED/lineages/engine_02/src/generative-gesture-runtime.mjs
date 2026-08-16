const LOGICAL_KEYS = new Set(['all', 'any', 'not']);
const LEAF_OPS = new Set(['truthy', 'gte', 'length_gte', 'equals', 'includes_any', 'family_any', 'topic_in']);

function isObject(value) {
  return value && typeof value === 'object' && !Array.isArray(value);
}

function pathParts(path) {
  return String(path ?? '').split('.').filter(Boolean);
}

export function getPath(root, path) {
  let value = root;
  for (const part of pathParts(path)) {
    if (value == null) return undefined;
    if (part === 'length' && (Array.isArray(value) || typeof value === 'string')) { value = value.length; continue; }
    value = value[part];
  }
  return value;
}

function scalar(value) {
  if (value == null) return '';
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return String(value);
  return JSON.stringify(value);
}

function resolveTemplatePath(context, token, locals = {}) {
  if (token === 'index') return locals.index ?? '';
  if (token === 'index1') return Number(locals.index ?? 0) + 1;
  if (token in locals) return locals[token];
  const localRoot = token.split('.')[0];
  if (localRoot in locals) return getPath(locals, token);
  return getPath(context, token);
}

export function renderTemplate(template, context, locals = {}) {
  if (template == null) return template;
  if (typeof template !== 'string') return template;
  const whole = template.match(/^\{\{\s*([^{}]+?)\s*\}\}$/u);
  if (whole) return resolveTemplatePath(context, whole[1].trim(), locals);
  return template.replace(/\{\{\s*([^{}]+?)\s*\}\}/gu, (_, token) => scalar(resolveTemplatePath(context, token.trim(), locals)));
}

function arrayValue(context, path) {
  const value = getPath(context, path);
  return Array.isArray(value) ? value : [];
}

export function evaluateRule(rule, context) {
  if (!isObject(rule)) return false;
  if (Array.isArray(rule.all)) return rule.all.every((item) => evaluateRule(item, context));
  if (Array.isArray(rule.any)) return rule.any.some((item) => evaluateRule(item, context));
  if (rule.not) return !evaluateRule(rule.not, context);
  const op = rule.op;
  if (!LEAF_OPS.has(op)) return false;
  const value = getPath(context, rule.path);
  if (op === 'truthy') return Boolean(value);
  if (op === 'gte') return Number(value ?? 0) >= Number(rule.value ?? 0);
  if (op === 'length_gte') return (Array.isArray(value) || typeof value === 'string' ? value.length : 0) >= Number(rule.value ?? 0);
  if (op === 'equals') return value === rule.value;
  if (op === 'includes_any') {
    const source = new Set(Array.isArray(value) ? value : []);
    return (rule.values ?? []).some((item) => source.has(item));
  }
  if (op === 'family_any') {
    const ids = new Set((context.families ?? []).map((family) => family.family_id));
    return (rule.values ?? []).some((item) => ids.has(item));
  }
  if (op === 'topic_in') return (rule.values ?? []).includes(context.hypothesis?.topic_id);
  return false;
}

export function evaluateGestureActivation(gesture, context) {
  const active = evaluateRule(gesture.activation, context);
  const reasonTemplate = active ? gesture.active_reason : gesture.inactive_reason;
  return {
    active,
    reason: String(renderTemplate(reasonTemplate ?? (active ? 'Declarative activation rule matched.' : 'Declarative activation rule did not match.'), context) ?? ''),
  };
}

function resolveParents(parentSpecs, emitted, questionNodeId) {
  const ids = [];
  for (const spec of parentSpecs ?? ['QUESTION']) {
    if (spec === 'QUESTION') {
      ids.push(questionNodeId);
      continue;
    }
    if (typeof spec === 'string' && spec.startsWith('NODE:')) {
      const key = spec.slice(5);
      for (const item of emitted.filter((entry) => entry.local_key === key)) ids.push(item.node.node_id);
      continue;
    }
    if (typeof spec === 'string' && spec.startsWith('ROLE:')) {
      const role = spec.slice(5);
      for (const item of emitted.filter((entry) => entry.node.role === role)) ids.push(item.node.node_id);
      continue;
    }
  }
  return [...new Set(ids)];
}

function expandedSpecs(spec, context) {
  if (!spec.for_each) return [{ spec, locals: {} }];
  const values = arrayValue(context, spec.for_each);
  return values.map((value, index) => ({ spec, locals: { [spec.as ?? 'item']: value, index } }));
}

export function emitGestureProgram(gesture, context, makeNode) {
  const emitted = [];
  for (const rawSpec of gesture.emission_program ?? []) {
    for (const { spec, locals } of expandedSpecs(rawSpec, context)) {
      if (spec.when && !evaluateRule(spec.when, { ...context, ...locals })) continue;
      const role = String(renderTemplate(spec.role, context, locals));
      const key = String(renderTemplate(spec.node_key, context, locals));
      const title = String(renderTemplate(spec.title, context, locals));
      const proposition = String(renderTemplate(spec.proposition, context, locals));
      const residualRaw = renderTemplate(spec.residual_kind ?? null, context, locals);
      const residualKind = residualRaw == null || residualRaw === '' ? null : String(residualRaw);
      const parents = resolveParents(spec.parents, emitted, context.questionNode.node_id);
      const node = makeNode({ role, key, title, proposition, parents, residualKind });
      emitted.push({ local_key: key, node });
    }
  }
  return emitted.map((entry) => entry.node);
}

function validateRule(rule, at, errors) {
  if (!isObject(rule)) { errors.push(`${at}: activation rule must be an object.`); return; }
  for (const key of LOGICAL_KEYS) {
    if (!(key in rule)) continue;
    if (key === 'not') validateRule(rule.not, `${at}.not`, errors);
    else {
      if (!Array.isArray(rule[key]) || !rule[key].length) errors.push(`${at}.${key}: must be a non-empty array.`);
      else rule[key].forEach((child, index) => validateRule(child, `${at}.${key}[${index}]`, errors));
    }
    return;
  }
  if (!LEAF_OPS.has(rule.op)) errors.push(`${at}.op: unsupported leaf operator ${String(rule.op)}.`);
  if (!['family_any', 'topic_in'].includes(rule.op) && !String(rule.path ?? '').trim()) errors.push(`${at}.path: required.`);
}

export function validateDeclarativeGestures(registry) {
  const errors = [];
  if (!Array.isArray(registry?.generative_gestures) || !registry.generative_gestures.length) return ['generative_gestures must be a non-empty array.'];
  const ids = registry.generative_gestures.map((g) => g?.gesture_id).filter(Boolean);
  if (new Set(ids).size !== ids.length) errors.push('generative_gestures contains duplicate gesture_id values.');
  for (const [index, gesture] of registry.generative_gestures.entries()) {
    const at = `generative_gestures[${index}]`;
    if (!String(gesture?.gesture_id ?? '').trim()) errors.push(`${at}.gesture_id: required.`);
    if (!Array.isArray(gesture?.protocol_refs) || !gesture.protocol_refs.length) errors.push(`${at}.protocol_refs: at least one protocol ref is required.`);
    validateRule(gesture?.activation, `${at}.activation`, errors);
    if (!Array.isArray(gesture?.emission_program) || !gesture.emission_program.length) errors.push(`${at}.emission_program: non-empty array required.`);
    else {
      const declaredOutputs = new Set(gesture.outputs ?? []);
      const emittedRoles = new Set(gesture.emission_program.map((spec) => spec?.role).filter((role) => typeof role === 'string' && !role.includes('{{')));
      for (const role of emittedRoles) if (!declaredOutputs.has(role)) errors.push(`${at}.outputs: missing emitted role ${role}.`);
      for (const [i, spec] of gesture.emission_program.entries()) {
        for (const field of ['role', 'node_key', 'title', 'proposition']) if (!String(spec?.[field] ?? '').trim()) errors.push(`${at}.emission_program[${i}].${field}: required.`);
        if (spec?.for_each && !String(spec.as ?? '').trim()) errors.push(`${at}.emission_program[${i}].as: required when for_each is used.`);
      }
    }
  }
  return errors;
}
