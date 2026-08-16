function deepEqual(a,b){
  if (Object.is(a,b)) return true;
  if (typeof a!==typeof b || a===null || b===null) return false;
  if (Array.isArray(a)) return Array.isArray(b) && a.length===b.length && a.every((v,i)=>deepEqual(v,b[i]));
  if (typeof a==='object'){
    const ka=Object.keys(a), kb=Object.keys(b);
    if(ka.length!==kb.length) return false;
    return ka.every(k=>Object.prototype.hasOwnProperty.call(b,k)&&deepEqual(a[k],b[k]));
  }
  return false;
}
function esc(s){return String(s).replace(/~/g,'~0').replace(/\//g,'~1')}
function resolvePointer(root,ref){
  if(ref==='#') return root;
  if(!ref.startsWith('#/')) throw new Error(`Unsupported $ref ${ref}`);
  let cur=root;
  for(const raw of ref.slice(2).split('/')){
    const k=raw.replace(/~1/g,'/').replace(/~0/g,'~');
    cur=cur?.[k];
  }
  if(cur===undefined) throw new Error(`Unresolved $ref ${ref}`);
  return cur;
}
function typeOk(data,t){
  switch(t){
    case 'null': return data===null;
    case 'array': return Array.isArray(data);
    case 'object': return data!==null && typeof data==='object' && !Array.isArray(data);
    case 'string': return typeof data==='string';
    case 'boolean': return typeof data==='boolean';
    case 'number': return typeof data==='number' && Number.isFinite(data);
    case 'integer': return typeof data==='number' && Number.isInteger(data);
    default: return true;
  }
}
function makeErr(instancePath,schemaPath,keyword,message,params={}){return {instancePath,schemaPath,keyword,message,params}}
function validateSchema(schema,data,root,instancePath='',schemaPath='',allErrors=true){
  const errs=[];
  const push=(e)=>{errs.push(e); return !allErrors};
  if(schema===true) return errs;
  if(schema===false){push(makeErr(instancePath,schemaPath,'false schema','must NOT be valid')); return errs;}
  if(!schema || typeof schema!=='object') return errs;

  if(schema.$ref){
    const target=resolvePointer(root,schema.$ref);
    const sub=validateSchema(target,data,root,instancePath,schema.$ref,allErrors);
    errs.push(...sub); if(sub.length&&!allErrors) return errs;
  }
  if('type' in schema){
    const types=Array.isArray(schema.type)?schema.type:[schema.type];
    if(!types.some(t=>typeOk(data,t))){push(makeErr(instancePath,`${schemaPath}/type`,'type',`must be ${types.join(',')}`,{type:schema.type})); return errs;}
  }
  if('const' in schema && !deepEqual(data,schema.const)){if(push(makeErr(instancePath,`${schemaPath}/const`,'const','must be equal to constant',{allowedValue:schema.const})))return errs;}
  if(Array.isArray(schema.enum) && !schema.enum.some(v=>deepEqual(data,v))){if(push(makeErr(instancePath,`${schemaPath}/enum`,'enum','must be equal to one of the allowed values',{allowedValues:schema.enum})))return errs;}
  if(typeof data==='string'){
    const n=[...data].length;
    if(Number.isInteger(schema.minLength)&&n<schema.minLength){if(push(makeErr(instancePath,`${schemaPath}/minLength`,'minLength',`must NOT have fewer than ${schema.minLength} characters`,{limit:schema.minLength})))return errs;}
    if(Number.isInteger(schema.maxLength)&&n>schema.maxLength){if(push(makeErr(instancePath,`${schemaPath}/maxLength`,'maxLength',`must NOT have more than ${schema.maxLength} characters`,{limit:schema.maxLength})))return errs;}
    if(typeof schema.pattern==='string'){
      let ok=true; try{ok=new RegExp(schema.pattern,'u').test(data)}catch{ok=new RegExp(schema.pattern).test(data)}
      if(!ok){if(push(makeErr(instancePath,`${schemaPath}/pattern`,'pattern',`must match pattern ${schema.pattern}`,{pattern:schema.pattern})))return errs;}
    }
  }
  if(typeof data==='number'&&Number.isFinite(data)){
    if(typeof schema.minimum==='number'&&data<schema.minimum){if(push(makeErr(instancePath,`${schemaPath}/minimum`,'minimum',`must be >= ${schema.minimum}`,{comparison:'>=',limit:schema.minimum})))return errs;}
    if(typeof schema.maximum==='number'&&data>schema.maximum){if(push(makeErr(instancePath,`${schemaPath}/maximum`,'maximum',`must be <= ${schema.maximum}`,{comparison:'<=',limit:schema.maximum})))return errs;}
    if(typeof schema.exclusiveMinimum==='number'&&data<=schema.exclusiveMinimum){if(push(makeErr(instancePath,`${schemaPath}/exclusiveMinimum`,'exclusiveMinimum',`must be > ${schema.exclusiveMinimum}`,{comparison:'>',limit:schema.exclusiveMinimum})))return errs;}
    if(typeof schema.exclusiveMaximum==='number'&&data>=schema.exclusiveMaximum){if(push(makeErr(instancePath,`${schemaPath}/exclusiveMaximum`,'exclusiveMaximum',`must be < ${schema.exclusiveMaximum}`,{comparison:'<',limit:schema.exclusiveMaximum})))return errs;}
    if(typeof schema.multipleOf==='number'&&schema.multipleOf!==0){const q=data/schema.multipleOf;if(Math.abs(q-Math.round(q))>1e-12){if(push(makeErr(instancePath,`${schemaPath}/multipleOf`,'multipleOf',`must be multiple of ${schema.multipleOf}`,{multipleOf:schema.multipleOf})))return errs;}}
  }
  if(Array.isArray(data)){
    if(Number.isInteger(schema.minItems)&&data.length<schema.minItems){if(push(makeErr(instancePath,`${schemaPath}/minItems`,'minItems',`must NOT have fewer than ${schema.minItems} items`,{limit:schema.minItems})))return errs;}
    if(Number.isInteger(schema.maxItems)&&data.length>schema.maxItems){if(push(makeErr(instancePath,`${schemaPath}/maxItems`,'maxItems',`must NOT have more than ${schema.maxItems} items`,{limit:schema.maxItems})))return errs;}
    if(schema.uniqueItems){outer:for(let i=0;i<data.length;i++)for(let j=i+1;j<data.length;j++)if(deepEqual(data[i],data[j])){if(push(makeErr(instancePath,`${schemaPath}/uniqueItems`,'uniqueItems','must NOT have duplicate items',{i,j})))return errs;break outer;}}
    if(Array.isArray(schema.prefixItems)){
      for(let i=0;i<Math.min(data.length,schema.prefixItems.length);i++){const sub=validateSchema(schema.prefixItems[i],data[i],root,`${instancePath}/${i}`,`${schemaPath}/prefixItems/${i}`,allErrors);errs.push(...sub);if(sub.length&&!allErrors)return errs;}
    }
    if(schema.items && !Array.isArray(schema.items)){
      const start=Array.isArray(schema.prefixItems)?schema.prefixItems.length:0;
      for(let i=start;i<data.length;i++){const sub=validateSchema(schema.items,data[i],root,`${instancePath}/${i}`,`${schemaPath}/items`,allErrors);errs.push(...sub);if(sub.length&&!allErrors)return errs;}
    }
  }
  if(data!==null && typeof data==='object' && !Array.isArray(data)){
    const keys=Object.keys(data);
    if(Number.isInteger(schema.minProperties)&&keys.length<schema.minProperties){if(push(makeErr(instancePath,`${schemaPath}/minProperties`,'minProperties',`must NOT have fewer than ${schema.minProperties} properties`,{limit:schema.minProperties})))return errs;}
    if(Number.isInteger(schema.maxProperties)&&keys.length>schema.maxProperties){if(push(makeErr(instancePath,`${schemaPath}/maxProperties`,'maxProperties',`must NOT have more than ${schema.maxProperties} properties`,{limit:schema.maxProperties})))return errs;}
    if(Array.isArray(schema.required)) for(const k of schema.required) if(!Object.prototype.hasOwnProperty.call(data,k)){if(push(makeErr(instancePath,`${schemaPath}/required`,'required',`must have required property '${k}'`,{missingProperty:k})))return errs;}
    if(schema.properties && typeof schema.properties==='object') for(const [k,subschema] of Object.entries(schema.properties)) if(Object.prototype.hasOwnProperty.call(data,k)){
      const sub=validateSchema(subschema,data[k],root,`${instancePath}/${esc(k)}`,`${schemaPath}/properties/${esc(k)}`,allErrors);errs.push(...sub);if(sub.length&&!allErrors)return errs;
    }
    const matchedByPattern=new Set();
    if(schema.patternProperties && typeof schema.patternProperties==='object'){
      for(const [pat,subschema] of Object.entries(schema.patternProperties)){
        const re=new RegExp(pat,'u');
        for(const k of keys) if(re.test(k)){matchedByPattern.add(k);const sub=validateSchema(subschema,data[k],root,`${instancePath}/${esc(k)}`,`${schemaPath}/patternProperties/${esc(pat)}`,allErrors);errs.push(...sub);if(sub.length&&!allErrors)return errs;}
      }
    }
    if(schema.additionalProperties===false){
      const allowed=new Set(Object.keys(schema.properties||{}));
      for(const k of keys) if(!allowed.has(k)&&!matchedByPattern.has(k)){if(push(makeErr(instancePath,`${schemaPath}/additionalProperties`,'additionalProperties','must NOT have additional properties',{additionalProperty:k})))return errs;}
    } else if(schema.additionalProperties && typeof schema.additionalProperties==='object'){
      const allowed=new Set(Object.keys(schema.properties||{}));
      for(const k of keys) if(!allowed.has(k)&&!matchedByPattern.has(k)){const sub=validateSchema(schema.additionalProperties,data[k],root,`${instancePath}/${esc(k)}`,`${schemaPath}/additionalProperties`,allErrors);errs.push(...sub);if(sub.length&&!allErrors)return errs;}
    }
  }
  if(Array.isArray(schema.allOf)) for(let i=0;i<schema.allOf.length;i++){const sub=validateSchema(schema.allOf[i],data,root,instancePath,`${schemaPath}/allOf/${i}`,allErrors);errs.push(...sub);if(sub.length&&!allErrors)return errs;}
  if(Array.isArray(schema.anyOf)){
    const valids=schema.anyOf.map((s,i)=>validateSchema(s,data,root,instancePath,`${schemaPath}/anyOf/${i}`,true));
    if(!valids.some(e=>e.length===0)){if(push(makeErr(instancePath,`${schemaPath}/anyOf`,'anyOf','must match a schema in anyOf',{})))return errs;}
  }
  if(Array.isArray(schema.oneOf)){
    const count=schema.oneOf.reduce((n,s,i)=>n+(validateSchema(s,data,root,instancePath,`${schemaPath}/oneOf/${i}`,true).length===0?1:0),0);
    if(count!==1){if(push(makeErr(instancePath,`${schemaPath}/oneOf`,'oneOf','must match exactly one schema in oneOf',{passingSchemas:null})))return errs;}
  }
  if(schema.not){const sub=validateSchema(schema.not,data,root,instancePath,`${schemaPath}/not`,true);if(sub.length===0){if(push(makeErr(instancePath,`${schemaPath}/not`,'not','must NOT be valid',{})))return errs;}}
  if(schema.if){
    const cond=validateSchema(schema.if,data,root,instancePath,`${schemaPath}/if`,true).length===0;
    if(cond&&schema.then){const sub=validateSchema(schema.then,data,root,instancePath,`${schemaPath}/then`,allErrors);errs.push(...sub);if(sub.length&&!allErrors)return errs;}
    if(!cond&&schema.else){const sub=validateSchema(schema.else,data,root,instancePath,`${schemaPath}/else`,allErrors);errs.push(...sub);if(sub.length&&!allErrors)return errs;}
  }
  return errs;
}

export default class Ajv2020Compat {
  constructor(options={}){this.options=options;}
  compile(schema){
    const root=schema;
    const validate=(data)=>{const errors=validateSchema(root,data,root,'','',this.options.allErrors!==false);validate.errors=errors.length?errors:null;return errors.length===0;};
    validate.errors=null;
    return validate;
  }
}
