import {ArrowRight,ArrowUpRight,FileText,Globe2,Languages,Landmark,Mail,MapPin,Phone,ShieldCheck,Stamp,BookOpen,Check} from 'lucide-react';
import './landing.css';

type Props={signedIn:boolean;onStart:()=>void};
const services=[
  {icon:Languages,title:'Dịch thuật',tag:'Đa ngôn ngữ',description:'Chuyển ngữ giấy tờ, tài liệu để kết nối với những hành trình quốc tế.'},
  {icon:Stamp,title:'Công chứng',tag:'Nhanh chóng',description:'Hỗ trợ công chứng giấy tờ cá nhân theo nhu cầu sử dụng hồ sơ.'},
  {icon:Landmark,title:'Hợp pháp hóa Bộ Ngoại giao',tag:'Chính thống',description:'Hỗ trợ thực hiện thủ tục hợp pháp hóa hồ sơ tại Bộ Ngoại giao.'},
  {icon:Globe2,title:'Hợp pháp hóa tại Đại sứ quán',tag:'Các nước',description:'Đồng hành cùng hồ sơ cần thực hiện thủ tục tại Đại sứ quán.'},
  {icon:ShieldCheck,title:'Hỗ trợ trọn gói',tag:'Từ A - Z',description:'Kết nối các bước xử lý, giúp bạn theo dõi hành trình của hồ sơ.'},
];
export function LandingPage({signedIn,onStart}:Props){
  const destination=signedIn?'/app':'/login';
  return <div className="landing-page">
    <header className="landing-header">
      <a className="landing-brand" href="/" aria-label="KUN GLOBAL trang chủ"><span className="brand-logo-frame"><img src="/kun-global-logo-v2.png" alt="KUN GLOBAL" width="1033" height="1042"/></span></a>
      <nav aria-label="Điều hướng trang giới thiệu"><a href="#dich-vu">Dịch vụ</a><a href="#ho-so">Hồ sơ cá nhân</a><a href="#lien-he">Liên hệ</a></nav>
      <a className="landing-header-phone" href="tel:+84986839092"><Phone size={15}/>0986.839.092</a>
      <a className="landing-login" href={destination} onClick={event=>{if(!event.ctrlKey&&!event.metaKey&&!event.shiftKey&&!event.altKey){event.preventDefault();onStart();}}}>{signedIn?'Mở ứng dụng':'Đăng nhập'}<ArrowUpRight size={16}/></a>
    </header>
    <section className="landing-banner" aria-label="Dịch vụ KUN GLOBAL"><img src="/kun-global-services-banner-v2.png" alt="KUN GLOBAL — Hợp pháp hóa lãnh sự giấy tờ cá nhân. Hồ sơ của bạn là trách nhiệm của chúng tôi." width="2055" height="765" fetchPriority="high"/></section>
    <main className="landing-main">
      <section className="landing-hero" aria-labelledby="landing-title">
        <div className="landing-hero-copy"><span className="landing-eyebrow">KUN GLOBAL · HỒ SƠ VƯƠN TẦM QUỐC TẾ</span><h1 id="landing-title">Hợp pháp hóa lãnh sự<br/><em>Giấy tờ cá nhân</em></h1><p>Từ dịch thuật, công chứng đến hợp pháp hóa tại Bộ Ngoại giao và Đại sứ quán. KUN GLOBAL đồng hành cùng hồ sơ của bạn trên hành trình ra thế giới.</p><div className="landing-hero-actions"><a className="landing-primary" href="tel:+84986839092"><Phone size={17}/>Liên hệ tư vấn<ArrowUpRight size={17}/></a><button className="landing-text-button" onClick={onStart}>Truy cập công cụ dịch<ArrowRight size={17}/></button></div></div>
        <aside className="landing-promise"><span className="landing-promise-mark" aria-hidden="true">“</span><blockquote>Hồ sơ của bạn<br/><em>Là trách nhiệm<br/>của chúng tôi!</em></blockquote><span className="landing-promise-sign">KUN GLOBAL</span><div className="landing-promise-line"/></aside>
      </section>
      <section className="landing-services" id="dich-vu" aria-labelledby="landing-services-title">
        <div className="landing-section-heading"><div><span className="landing-section-label"><span/>DỊCH VỤ CỦA CHÚNG TÔI</span><h2 id="landing-services-title">Hỗ trợ hồ sơ.<br/><em>Kết nối hành trình quốc tế.</em></h2></div><p>Từ dịch thuật đến hợp pháp hóa lãnh sự.<br/>Một đầu mối hỗ trợ cho hồ sơ của bạn.</p></div>
        <div className="landing-services-grid">{services.map(({icon:Icon,title,tag,description},index)=>
          <article key={title} className={`landing-service-card${index===4?' landing-service-featured':''}`}>
            <div className="landing-service-top"><span className="landing-service-icon"><Icon size={25} strokeWidth={1.6}/></span><span className="landing-service-tag">{tag}</span></div>
            <div className="landing-service-copy"><span className="landing-service-number">0{index+1} / KUN GLOBAL</span><h3>{title}</h3><p>{description}</p></div>
            {index===4&&<ul className="landing-service-includes"><li><Check size={16}/>Dịch thuật &amp; công chứng</li><li><Check size={16}/>Hợp pháp hóa Bộ Ngoại giao</li><li><Check size={16}/>Hợp pháp hóa tại Đại sứ quán</li></ul>}
            <a className="landing-service-link" href="#lien-he" aria-label={`Liên hệ về ${title.toLowerCase()}`}>{index===4?'Tư vấn hồ sơ của bạn':'Trao đổi nhu cầu'}<ArrowUpRight size={17}/></a>
          </article>
        )}</div>
      </section>
      <section className="landing-documents" id="ho-so" aria-labelledby="landing-documents-title">
        <div><span className="landing-section-label">GIẤY TỜ CÁ NHÂN</span><h2 id="landing-documents-title">Mỗi hồ sơ,<br/><em>một hành trình riêng.</em></h2><p>Giấy tờ quen thuộc hôm nay có thể là khởi đầu cho một chặng đường mới. Hãy trao đổi với KUN GLOBAL về loại hồ sơ và quốc gia bạn cần sử dụng.</p><a className="landing-dark-button" href="#lien-he">Tư vấn hồ sơ của bạn<ArrowRight size={17}/></a></div>
        <div className="landing-document-list"><div><FileText/><span><strong>Giấy khai sinh</strong><small>Hồ sơ cá nhân</small></span><Check size={18}/></div><div><BookOpen/><span><strong>Bằng tốt nghiệp</strong><small>Hồ sơ học tập</small></span><Check size={18}/></div><div><Globe2/><span><strong>Hộ chiếu</strong><small>Giấy tờ đi cùng hành trình</small></span><Check size={18}/></div></div>
      </section>
      <section className="landing-destinations" aria-labelledby="landing-destinations-title"><div><span className="landing-section-label">KẾT NỐI KHÔNG BIÊN GIỚI</span><h2 id="landing-destinations-title">Hồ sơ đi khắp thế giới.</h2></div><div className="landing-country-list">{['Hàn Quốc','Nhật Bản','Hoa Kỳ','Trung Quốc','Châu Âu'].map(country=><span key={country}><Globe2 size={15}/>{country}</span>)}</div></section>
      <section className="landing-how" aria-labelledby="landing-how-title"><div><span className="landing-section-label">ĐỒNG HÀNH TỪ A - Z</span><h2 id="landing-how-title">Bạn chia sẻ nhu cầu.<br/><em>Chúng tôi cùng bạn<br/>chuẩn bị hành trình.</em></h2><a className="landing-text-link" href="tel:+84986839092">Gọi 0986.839.092<ArrowUpRight size={17}/></a></div><ol className="landing-steps"><li><span>01</span><div><h3>Trao đổi nhu cầu</h3><p>Chia sẻ loại giấy tờ, mục đích và quốc gia sử dụng để được tư vấn hướng xử lý phù hợp.</p></div></li><li><span>02</span><div><h3>Chuẩn bị và thực hiện</h3><p>Thống nhất các bước dịch thuật, công chứng và hợp pháp hóa cần thiết cho hồ sơ.</p></div></li><li><span>03</span><div><h3>Theo dõi và nhận hồ sơ</h3><p>Giữ liên hệ với KUN GLOBAL trong quá trình thực hiện và nhận lại hồ sơ khi hoàn tất.</p></div></li></ol></section>
      <section className="landing-tool"><div className="landing-tool-icon"><Languages size={32}/></div><div><span className="landing-section-label">KHÔNG GIAN DỊCH THUẬT</span><h2>Công cụ dịch đa ngôn ngữ</h2><p>Văn bản, hình ảnh và tài liệu. Truy cập bằng tài khoản được cấp để bắt đầu dịch.</p><span className="landing-tool-formats">VĂN BẢN <i/> HÌNH ẢNH <i/> PDF · DOCX · TXT</span></div><button className="landing-primary" onClick={onStart}>{signedIn?'Mở ứng dụng dịch':'Đăng nhập để dịch'}<ArrowRight size={18}/></button></section>
      <section className="landing-contact" id="lien-he" aria-labelledby="landing-contact-title"><div className="landing-contact-heading"><span className="landing-section-label">LIÊN HỆ KUN GLOBAL</span><h2 id="landing-contact-title">Bắt đầu từ<br/><em>hồ sơ của bạn.</em></h2><p>Kết nối giá trị - Vươn tầm quốc tế</p><a className="landing-dark-button" href="tel:+84986839092"><Phone size={17}/>0986.839.092<ArrowUpRight size={17}/></a></div><div className="landing-contact-details"><div><MapPin size={22}/><span><small>ĐỊA CHỈ</small><p>Tầng 8, 52 Chùa Hà,<br/>Nghĩa Đô, Hà Nội</p></span></div><div><Mail size={22}/><span><small>EMAIL</small><a href="mailto:lienhekuni@gmail.com">lienhekuni@gmail.com<ArrowUpRight size={15}/></a></span></div><div><Globe2 size={22}/><span><small>WEBSITE</small><a href="https://datkun.com" target="_blank" rel="noopener noreferrer">datkun.com<ArrowUpRight size={15}/></a></span></div></div></section>
    </main>
    <footer className="landing-footer"><strong>KUN GLOBAL<span>KẾT NỐI GIÁ TRỊ - VƯƠN TẦM QUỐC TẾ</span></strong><span>© 2026 KUN GLOBAL</span><a href="#landing-title">Trở về đầu trang ↑</a></footer>
  </div>;
}
