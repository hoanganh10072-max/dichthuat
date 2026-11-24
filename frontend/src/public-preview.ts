// Enabled only for the public Netlify UI preview, never authentication.
export const PUBLIC_PREVIEW = import.meta.env.VITE_PUBLIC_PREVIEW === 'true';
export const PREVIEW_NOTICE = 'Bản xem giao diện · Chưa kết nối máy chủ. Đăng nhập, dịch và xuất tài liệu chưa hoạt động trên bản online này.';
export const PREVIEW_LANGUAGES = [
  {code:'vi',name:'Tiếng Việt'}, {code:'lo',name:'ພາສາລາວ · Tiếng Lào'}, {code:'en',name:'English'},
  {code:'th',name:'ไทย · Tiếng Thái'}, {code:'zh',name:'中文 · Tiếng Trung'}, {code:'km',name:'ខ្មែរ · Tiếng Khmer'},
  {code:'ja',name:'日本語 · Tiếng Nhật'}, {code:'ko',name:'한국어 · Tiếng Hàn'}, {code:'fr',name:'Français'},
  {code:'de',name:'Deutsch'}, {code:'es',name:'Español'}, {code:'ru',name:'Русский'}, {code:'id',name:'Bahasa Indonesia'},
  {code:'ms',name:'Bahasa Melayu'}, {code:'my',name:'မြန်မာ · Tiếng Myanmar'}, {code:'hi',name:'हिन्दी'},
  {code:'it',name:'Italiano · Tiếng Ý'}, {code:'pt',name:'Português · Tiếng Bồ Đào Nha'},
  {code:'nl',name:'Nederlands · Tiếng Hà Lan'}, {code:'ar',name:'العربية · Tiếng Ả Rập'},
];
