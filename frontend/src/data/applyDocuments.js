const VALIDITY_WAIT_FOR_MENTOR_NOTE =
  'Chỉ hiệu lực 6 tháng, không xin trước — đợi mentor dặn.';

export const APPLY_DOCUMENTS = [
  {
    id: 'photo',
    label: 'Chụp ảnh',
    hint: {
      lines: [
        'Xem tiêu chuẩn ảnh hồ sơ du học Trung Quốc tại link bên dưới.',
        'Sau khi chụp, nhớ xin file ảnh để apply online.',
        'In 4 chiếc để dán vào giấy khám sức khỏe và nộp visa nếu đỗ.',
      ],
      links: [
        {
          label: 'Tiêu chuẩn ảnh hồ sơ du học Trung Quốc',
          href: 'https://hanhdat.edu.vn/tieu-chuan-anh-ho-so-du-hoc-trung-quoc/',
        },
      ],
    },
  },
  {
    id: 'health',
    label: 'Giấy khám sức khỏe',
    validityNote: true,
    hint: {
      lines: [
        'TP.HCM: khám tại Hòa Hảo — nói rõ với bệnh viện là khám du học Trung Quốc.',
        'Hà Nội: khám tại Tràng An.',
        'Có form mẫu — nếu khám bệnh viện khác, hỏi rõ có hỗ trợ form này không.',
        VALIDITY_WAIT_FOR_MENTOR_NOTE,
      ],
      links: [
        {
          label: 'Form giấy khám sức khỏe (ĐSQ Trung Quốc)',
          href: 'https://br.china-embassy.gov.cn/por/whjy/201801/P020210801780704199692.pdf',
        },
      ],
    },
  },
  {
    id: 'passport',
    label: 'Hộ chiếu',
    hint: {
      lines: [
        'Scan mặt có ảnh và dấu — trang 2, 3.',
        'Nếu đã từng đi Trung Quốc: chụp thêm trang visa và dấu xuất nhập cảnh.',
      ],
    },
  },
  {
    id: 'criminal-record',
    label: 'Lý lịch tư pháp',
    validityNote: true,
    hint: {
      lines: [
        'Form số 1 hoặc số 2 đều được — mất khoảng 1 tháng để làm.',
        'Hoặc Xác nhận dân sự (1 ngày nếu địa phương chấp nhận).',
        VALIDITY_WAIT_FOR_MENTOR_NOTE,
      ],
    },
  },
  {
    id: 'diploma',
    label: 'Bằng tốt nghiệp',
    hint: {
      lines: [
        'Bằng tốt nghiệp ĐH/THPT hoặc giấy xác nhận đang là sinh viên/học sinh.',
        'Nếu là giấy xác nhận: ghi rõ dự kiến tốt nghiệp tháng 6–7/2027.',
        'Các bạn đã tốt nghiệp: cần hợp pháp hóa bằng thông qua trang chính chủ của CSC.',
        VALIDITY_WAIT_FOR_MENTOR_NOTE,
      ],
    },
  },
  {
    id: 'transcript',
    label: 'Bảng điểm',
    hint: {
      lines: ['Bảng điểm đại học hoặc cấp 3 (tùy hệ bạn apply).'],
    },
  },
  {
    id: 'language',
    label: 'Chứng chỉ ngoại ngữ',
    hint: {
      lines: ['Chứng chỉ ngoại ngữ liên quan (HSK, IELTS, TOEFL… tùy yêu cầu trường).'],
    },
  },
  {
    id: 'work',
    label: 'Giấy xác nhận công tác',
    optional: true,
    hint: {
      lines: [
        'Nếu có — nên xin để bổ sung hồ sơ.',
        'Tên tương đương trên hệ thống dịch: 工作证明 / Employment confirmation Letter.',
      ],
    },
  },
  {
    id: 'study-plan',
    label: 'Kế hoạch học tập',
    hint: {
      lines: [
        'Mentor sẽ soạn và tải lên giúp bạn — bạn chỉ cần xem và tải file.',
        'Tên tương đương trên hệ thống dịch: Study Plan / 来华计划书.',
      ],
    },
  },
  {
    id: 'award',
    label: 'Giấy khen',
    optional: true,
    hint: {
      lines: ['Các loại giấy khen bạn đã có — nộp nếu có.'],
    },
  },
  {
    id: 'research',
    label: 'Nghiên cứu / bài báo',
    optional: true,
    hint: {
      lines: ['Các bài nghiên cứu, bài báo sẵn có — nộp nếu có.'],
    },
  },
  {
    id: 'recommendation-1',
    label: 'Thư giới thiệu 1',
    hint: {
      lines: [
        'Hệ thạc sĩ: từ GS/PGS.',
        'Hệ đại học: từ hiệu trưởng và GVCN.',
        'Không có thì liên hệ mentor — có thể hỗ trợ qua CTI (khoảng 1,5 triệu/thư).',
      ],
    },
  },
  {
    id: 'recommendation-2',
    label: 'Thư giới thiệu 2',
    hint: {
      lines: [
        'Hệ thạc sĩ: từ GS/PGS.',
        'Hệ đại học: từ hiệu trưởng và GVCN.',
        'Không có thì liên hệ mentor — có thể hỗ trợ qua CTI (khoảng 1,5 triệu/thư).',
      ],
    },
  },
  {
    id: 'personal-declaration',
    label: 'Kê khai thông tin cá nhân',
    hint: {
      lines: [
        'Bấm "Tạo & mở form kê khai" — hệ thống tạo bản mẫu riêng (Google Docs hoặc file docx).',
        'Nếu chỉ có file docx, hãy tạo bản sao Google Docs và dán link online để mentor theo dõi realtime.',
        'Mỗi mentee chỉ tạo 1 lần; lần sau bấm "Mở form online" hoặc "Mở file kê khai" để chỉnh sửa.',
        'Điền càng chi tiết càng tốt để mentor viết kế hoạch học tập.',
      ],
      links: [
        {
          label: 'Xem bản mẫu gốc (Google Docs)',
          href: 'https://docs.google.com/document/d/1kqkknLDEgl55k6e_orngAfmkMbHCn2ND7_4BCfIG7ro/edit?tab=t.0',
        },
      ],
    },
  },
  {
    id: 'parents-id',
    label: 'CCCD của bố mẹ',
    hint: {
      lines: ['Scan CCCD (mặt trước và mặt sau) của bố và mẹ.'],
    },
  },
  {
    id: 'financial',
    label: 'Chứng minh tài chính (CMTC)',
    hint: {
      lines: [
        'Chứng minh số dư ngân hàng khoảng 150 triệu VNĐ.',
        'Làm song ngữ Việt – Anh và có quy đổi giá trị sang USD.',
      ],
    },
  },
  {
    id: 'cv',
    label: 'CV học thuật / Portfolio',
    hint: {
      lines: [
        'Mentor sẽ soạn CV và tải lên giúp bạn — bạn chỉ cần xem và tải file.',
        'Portfolio: chỉ cần với ngành truyền thông / nghệ thuật.',
        'Có thể làm dịch vụ lẻ (phụ thu phí).',
        'Scan ngoài hàng cho đẹp hoặc dùng app Scan Genius trên điện thoại (icon màu cam).',
      ],
    },
  },
];

export const APPLY_GENERAL_NOTES = [
  'Tất cả giấy tờ cần dịch công chứng sang tiếng Anh hoặc tiếng Trung. Không tiện thì nhắn mentor — mentor gửi chỗ làm online, chỉ cần scan PDF.',
  'Mỗi mục giấy tờ scan thành 1 file PDF riêng.',
];

export const MENTOR_APPLY_SETUP = {
  'Thanh Hà': {
    forwardEmail: 'cherrythanh06@gmail.com',
  },
  'Mai Chi': {
    forwardEmail: 'mochisjtu@gmail.com',
  },
};

export const MENTOR_FORWARD_GUIDE = {
  label: 'Hướng dẫn cài forward email (Gmail)',
  href: 'https://support.google.com/mail/answer/10957?hl=vi',
};

export function getMentorApplyNote(mentorName) {
  const config = MENTOR_APPLY_SETUP[mentorName];
  if (!config) return '';
  return `Bạn cần tạo 1 mail clone và cài forward toàn bộ email tới ${config.forwardEmail} để mentor vào upload hồ sơ giúp bạn.`;
}
