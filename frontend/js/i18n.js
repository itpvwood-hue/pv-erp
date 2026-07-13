/* PVWood ERP - i18n shell strings + helpers.
   Extracted from index.html so language data + setLang/applyI18n live in
   one editable file. Globals declared at top-level here are visible to
   the main inline script (shared global lexical environment):
       _LANG, I18N, t, applyI18n, setLang, loginRebrand
*/
// ══════════════════════════════════════════════════════════
// I18N — shell-string translations (English / Thai / 简体中文)
// ══════════════════════════════════════════════════════════
// Each key is the English source. TH/ZH translations are best-effort and
// should be reviewed by a native speaker before factory rollout. To edit:
//   - find the key in this file
//   - update 'th' and 'zh' values
// To add a new translatable string in HTML, use either:
//   <span data-i18n="My label"></span>            ← replaces textContent
//   <input data-i18n-ph="Placeholder text">       ← replaces placeholder
//   <button title="..." data-i18n-title="...">    ← replaces title attr
// In JS, call t('My label') anywhere you previously had the literal.
// Strings not in the dict fall through to English untouched.
const I18N = {
  // ── meta / shell ────────────────────────────────────────────
  'PVWood ERP':                {th:'PVWood ERP',                       zh:'PVWood ERP'},
  'Factory Management':         {th:'การจัดการโรงงาน',                  zh:'工厂管理'},
  'Language':                   {th:'ภาษา',                             zh:'语言'},
  'English':                    {th:'English',                          zh:'English'},
  'Thai':                       {th:'ไทย',                              zh:'泰语'},
  'Simplified Chinese':         {th:'จีนตัวย่อ',                         zh:'简体中文'},
  // ── nav sections ────────────────────────────────────────────
  'Planning':                   {th:'การวางแผน',                        zh:'计划'},
  'Production Module':          {th:'โมดูลการผลิต',                      zh:'生产模块'},
  'FG Warehouse':               {th:'คลังสินค้าสำเร็จรูป',                zh:'成品仓库'},
  'Warehouse':                  {th:'คลังสินค้า',                        zh:'仓库'},
  'Finance':                    {th:'การเงิน',                           zh:'财务'},
  // ── sidebar entries (high-traffic) ──────────────────────────
  'Dashboard':                  {th:'แดชบอร์ด',                          zh:'仪表板'},
  'Order Intake':               {th:'รับคำสั่งซื้อ',                      zh:'订单录入'},
  'Line Board':                 {th:'กระดานสายการผลิต',                  zh:'生产线看板'},
  'Capacity Planning':          {th:'การวางแผนกำลังการผลิต',              zh:'产能计划'},
  'Material Shortfalls':        {th:'วัสดุขาดแคลน',                       zh:'物料短缺'},
  'Raw Materials & Consumables':{th:'วัตถุดิบและวัสดุสิ้นเปลือง',           zh:'原料与耗材'},
  'Finished Goods (FG)':        {th:'สินค้าสำเร็จรูป (FG)',                zh:'成品 (FG)'},
  'Bill of Materials':          {th:'รายการวัสดุ (BOM)',                  zh:'物料清单 (BOM)'},
  'BOM AI Query':               {th:'สอบถาม BOM ด้วย AI',                 zh:'BOM AI 查询'},
  'VCMX Orders':                {th:'คำสั่งผลิต VCMX',                    zh:'VCMX 订单'},
  'FC Hub':                     {th:'ศูนย์ FC',                          zh:'FC 中心'},
  'Station Leader Hub':         {th:'ศูนย์หัวหน้าสถานี',                  zh:'工位班长中心'},
  'VCMX Laminating (P01)':      {th:'การอัด VCMX (P01)',                  zh:'VCMX 层压 (P01)'},
  'Scrap / LG Bin':             {th:'ถังเศษ / LG',                       zh:'废料 / LG 桶'},
  'Prod Reports':               {th:'รายงานการผลิต',                     zh:'生产报告'},
  'Production Logs':            {th:'บันทึกการผลิต',                     zh:'生产日志'},
  'Daily Reports':              {th:'รายงานประจำวัน',                    zh:'每日报告'},
  'Forklift Report':            {th:'รายงานรถยก',                        zh:'叉车报告'},
  'Employees':                  {th:'พนักงาน',                          zh:'员工'},
  'Supply Queue':               {th:'คิวจัดส่งวัสดุ',                     zh:'供应队列'},
  'Admin Portal':               {th:'พอร์ทัลแอดมิน',                     zh:'管理员门户'},
  'Supply':                     {th:'จัดส่ง',                            zh:'供应'},
  'Request Consumables':        {th:'ขอวัสดุสิ้นเปลือง',                  zh:'请求耗材'},
  'Warehouse Ops':              {th:'ปฏิบัติการคลังสินค้า',                zh:'仓库作业'},
  'Raw Material Receiving':     {th:'รับวัตถุดิบ',                        zh:'原料接收'},
  'Forklift Refueling':         {th:'เติมเชื้อเพลิงรถยก',                  zh:'叉车加油'},
  'Forklift Dashboard':         {th:'แดชบอร์ดรถยก',                      zh:'叉车仪表板'},
  'Cost Analysis':              {th:'วิเคราะห์ต้นทุน',                     zh:'成本分析'},
  'Dept Costs':                 {th:'ต้นทุนแผนก',                        zh:'部门成本'},
  'Finance Portal':             {th:'พอร์ทัลการเงิน',                     zh:'财务门户'},
  'Administration':             {th:'การบริหาร',                         zh:'管理'},
  // ── login screen ────────────────────────────────────────────
  'Sign In':                    {th:'เข้าสู่ระบบ',                        zh:'登录'},
  'Username':                   {th:'ชื่อผู้ใช้',                          zh:'用户名'},
  'Password':                   {th:'รหัสผ่าน',                          zh:'密码'},
  'Forgot password?':           {th:'ลืมรหัสผ่าน?',                       zh:'忘记密码？'},
  'Invalid username or password': {th:'ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง',     zh:'用户名或密码错误'},
  'Factory Management System':  {th:'ระบบการจัดการโรงงาน',                zh:'工厂管理系统'},
  'Enter your username':        {th:'กรอกชื่อผู้ใช้',                      zh:'请输入用户名'},
  'Enter your password':        {th:'กรอกรหัสผ่าน',                       zh:'请输入密码'},
  'Hold to show password':      {th:'กดค้างเพื่อแสดงรหัสผ่าน',              zh:'按住以显示密码'},
  'Still having trouble? Contact your system administrator to reset your password.':
                                {th:'ยังเข้าสู่ระบบไม่ได้? ติดต่อผู้ดูแลระบบเพื่อรีเซ็ตรหัสผ่าน',
                                 zh:'还有问题？请联系系统管理员重置密码。'},
  // ── common buttons / actions ────────────────────────────────
  'Save':                       {th:'บันทึก',                            zh:'保存'},
  'Cancel':                     {th:'ยกเลิก',                            zh:'取消'},
  'Confirm':                    {th:'ยืนยัน',                            zh:'确认'},
  'Submit':                     {th:'ส่ง',                              zh:'提交'},
  'Submit Request':             {th:'ส่งคำขอ',                          zh:'提交请求'},
  'Refresh':                    {th:'รีเฟรช',                            zh:'刷新'},
  'Close':                      {th:'ปิด',                              zh:'关闭'},
  'Delete':                     {th:'ลบ',                               zh:'删除'},
  'Edit':                       {th:'แก้ไข',                             zh:'编辑'},
  'Add':                        {th:'เพิ่ม',                             zh:'添加'},
  'Search':                     {th:'ค้นหา',                            zh:'搜索'},
  'Filter':                     {th:'ตัวกรอง',                          zh:'筛选'},
  'Filters:':                   {th:'ตัวกรอง:',                          zh:'筛选条件:'},
  'Clear':                      {th:'ล้าง',                             zh:'清除'},
  'Export':                     {th:'ส่งออก',                            zh:'导出'},
  'Logout':                     {th:'ออกจากระบบ',                        zh:'退出登录'},
  'Loading…':                   {th:'กำลังโหลด…',                       zh:'加载中…'},
  // ── status / priority badges ────────────────────────────────
  'Status':                     {th:'สถานะ',                            zh:'状态'},
  'Priority':                   {th:'ลำดับความสำคัญ',                    zh:'优先级'},
  'PENDING':                    {th:'รอดำเนินการ',                       zh:'待处理'},
  'PARTIAL':                    {th:'บางส่วน',                          zh:'部分完成'},
  'FULFILLED':                  {th:'สำเร็จ',                            zh:'已完成'},
  'CANCELLED':                  {th:'ยกเลิกแล้ว',                        zh:'已取消'},
  'APPROVED':                   {th:'อนุมัติแล้ว',                        zh:'已批准'},
  'RECEIVED':                   {th:'รับแล้ว',                           zh:'已接收'},
  'P1 Urgent':                  {th:'P1 ด่วน',                          zh:'P1 紧急'},
  'P1':                         {th:'P1',                              zh:'P1'},
  'P2':                         {th:'P2',                              zh:'P2'},
  'P3':                         {th:'P3',                              zh:'P3'},
  'Morning':                    {th:'เช้า',                             zh:'上午'},
  'Afternoon':                  {th:'บ่าย',                             zh:'下午'},
  '— Any time —':               {th:'— เวลาใดก็ได้ —',                   zh:'— 任意时间 —'},
  '— Any —':                    {th:'— ใดก็ได้ —',                       zh:'— 任意 —'},
  // ── role labels ─────────────────────────────────────────────
  'Managerial':                 {th:'ผู้บริหาร',                          zh:'管理层'},
  'Production Planning':        {th:'วางแผนการผลิต',                     zh:'生产计划'},
  'Department Leader':          {th:'หัวหน้าแผนก',                       zh:'部门主管'},
  'Warehouse Staff':            {th:'พนักงานคลังสินค้า',                  zh:'仓库员工'},
  // ── common modal labels ─────────────────────────────────────
  'Material':                   {th:'วัสดุ',                             zh:'物料'},
  'Quantity':                   {th:'จำนวน',                             zh:'数量'},
  'Department':                 {th:'แผนก',                             zh:'部门'},
  'Line':                       {th:'สายการผลิต',                       zh:'生产线'},
  'Notes':                      {th:'หมายเหตุ',                          zh:'备注'},
  'Needed By':                  {th:'ต้องการภายใน',                      zh:'需求日期'},
  'Required Time':              {th:'เวลาที่ต้องการ',                     zh:'需求时间'},
  'Required Date':              {th:'วันที่ต้องการ',                     zh:'需求日期'},
  'New Consumable Request':     {th:'คำขอวัสดุสิ้นเปลืองใหม่',             zh:'新建耗材请求'},
  'Request Material Transfer to FC': {th:'ขอโอนวัสดุไปยัง FC',           zh:'请求物料调拨至 FC'},
  'New Purchase Request':       {th:'คำขอจัดซื้อใหม่',                   zh:'新建采购请求'},
  // ── stations ────────────────────────────────────────────────
  'Glue Mixing':                {th:'ผสมกาว',                           zh:'调胶'},
  'Laminating':                 {th:'การอัด',                            zh:'层压'},
  'Cold Press':                 {th:'อัดเย็น',                           zh:'冷压'},
  'Hot Press':                  {th:'อัดร้อน',                           zh:'热压'},
  'Sanding':                    {th:'ขัด',                              zh:'打磨'},
  'Repair':                     {th:'ซ่อม',                             zh:'修补'},
  'Grading':                    {th:'คัดเกรด',                           zh:'分级'},
  'Packing':                    {th:'บรรจุ',                            zh:'包装'},
};

let _LANG = (function(){
  const v = localStorage.getItem('erp_lang') || 'en';
  return (v === 'th' || v === 'zh') ? v : 'en';
})();

function t(key){
  if(!key || _LANG === 'en') return key;
  const entry = I18N[key];
  if(!entry) return key;        // fall through to source text
  return entry[_LANG] || key;
}

// Apply translations to every element marked with data-i18n* attributes.
// Safe to call repeatedly (e.g. after dynamic rendering).
function applyI18n(root){
  root = root || document;
  root.querySelectorAll('[data-i18n]').forEach(el => {
    const k = el.getAttribute('data-i18n'); el.textContent = t(k);
  });
  root.querySelectorAll('[data-i18n-ph]').forEach(el => {
    const k = el.getAttribute('data-i18n-ph'); el.setAttribute('placeholder', t(k));
  });
  root.querySelectorAll('[data-i18n-title]').forEach(el => {
    const k = el.getAttribute('data-i18n-title'); el.setAttribute('title', t(k));
  });
}

function setLang(lang){
  if(!['en','th','zh'].includes(lang)) lang = 'en';
  _LANG = lang;
  localStorage.setItem('erp_lang', lang);
  document.documentElement.setAttribute('lang', lang === 'zh' ? 'zh-Hans' : lang);
  applyI18n();
  // Mark switcher
  document.querySelectorAll('[data-lang-pick]').forEach(el => {
    el.classList.toggle('active-lang', el.getAttribute('data-lang-pick') === lang);
    if(el.classList.contains('login-lang-btn')){
      el.classList.toggle('btn-primary', el.getAttribute('data-lang-pick') === lang);
      el.classList.toggle('btn-outline-secondary', el.getAttribute('data-lang-pick') !== lang);
    }
  });
  // Re-render dynamic UI that has labels baked in (best-effort)
  try { typeof slhUpdateHeader === 'function' && slhUpdateHeader(); } catch{}
  // Materials description column reads name_th when _LANG==='th' — refresh it.
  try { if(typeof _renderMatFiltered === 'function' && Array.isArray(_allMaterials) && _allMaterials.length) _renderMatFiltered(); } catch{}
}
function loginRebrand(){ /* alias kept for login-screen language buttons */ }

document.addEventListener('DOMContentLoaded', () => {
  document.documentElement.setAttribute('lang', _LANG === 'zh' ? 'zh-Hans' : _LANG);
  applyI18n();
  // Mark current language in any picker that exists
  document.querySelectorAll('[data-lang-pick]').forEach(el => {
    el.classList.toggle('active-lang', el.getAttribute('data-lang-pick') === _LANG);
  });
});
