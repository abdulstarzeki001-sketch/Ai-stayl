import{a as e,n as t}from"./jsx-runtime-B-hcVAMW.js";
import{r as i}from"./router-compat-C4exDZeC.js";
import{t as a}from"./client-DcPTJvB5.js";
var o=e(t(),1),m=o.createContext(null);
function decodeJwt(e){if(!e?.access_token)return null;try{let t=e.access_token.split(".")[1];return JSON.parse(atob(t.replace(/-/g,"+").replace(/_/g,"/")))}catch{return null}}
function getSessionId(e){let t=decodeJwt(e);return typeof t?.session_id==="string"&&t.session_id.length?t.session_id:null}
function getIssuedAt(e){let t=decodeJwt(e);return typeof t?.iat==="number"?t.iat:null}
async function logEvent(){}
function AuthProvider({children:e}){
 const [user,tUser]=o.useState(null),[session,tSession]=o.useState(null),[loading,tLoading]=o.useState(true),navigate=i();
 o.useEffect(()=>{
  let active=true;
  const {data:{subscription}}=a.auth.onAuthStateChange((_event,next)=>{
   if(!active)return;
   tSession(next);tUser(next?.user??null);tLoading(false);
  });
  a.auth.getSession().then(({data,error})=>{
   if(!active)return;
   if(error)console.warn("Supabase session restore failed:",error.message);
   tSession(data?.session??null);tUser(data?.session?.user??null);tLoading(false);
  }).catch(error=>{if(active){console.warn("Supabase session restore failed:",error);tLoading(false)}});
  return()=>{active=false;subscription.unsubscribe()};
 },[]);
 const signUp=o.useCallback(async(email,password,username,referralCode)=>{
  try{
   const {data,error}=await a.auth.signUp({email,password,options:{data:{username,...(referralCode?{referral_code:referralCode}:{})}}});
   return {error:error?{message:error.message,code:error.code}:null,session:data?.session??null};
  }catch(error){return {error:{message:error?.message||"Signup failed"}}}
 },[]);
 const signIn=o.useCallback(async(email,password)=>{
  try{
   const {data,error}=await a.auth.signInWithPassword({email,password});
   if(error){
    const needsVerification=error.code==="email_not_confirmed"||/email not confirmed/i.test(error.message||"");
    return {error:{message:error.message||"Login failed",code:error.code,requiresVerification:needsVerification,email}};
   }
   return {error:null,session:data?.session??null};
  }catch(error){return {error:{message:error?.message||"Login failed"}}}
 },[]);
 const signOut=o.useCallback(async(reason)=>{
  try{
   if(reason)try{sessionStorage.setItem("logout_reason",reason)}catch{}
   const {error}=await a.auth.signOut({scope:"local"});
   if(!error)navigate("/auth");
   return {error:error??null};
  }catch(error){return {error}}
 },[navigate]);
 const value=o.useMemo(()=>({user,session,loading,signUp,signIn,signOut}),[user,session,loading,signUp,signIn,signOut]);
 return o.createElement(m.Provider,{value},e);
}
function useAuth(){const value=o.useContext(m);if(!value)throw Error("useAuth must be used within AuthProvider");return value}
export{logEvent as a,getIssuedAt as i,useAuth as n,getSessionId as r,AuthProvider as t};
