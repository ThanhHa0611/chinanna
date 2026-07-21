// Câu truyền động lực cho mentee đang apply học bổng du học — random mỗi lần vào trang

export const MOTIVATIONAL_QUOTES = [
  { text: 'Mọi nỗ lực hôm nay sẽ được đền đáp xứng đáng.' },
  { text: 'Hành trình du học bắt đầu từ sự kiên trì mỗi ngày, không phải từ một đêm may mắn.' },
  { text: 'Hồ sơ hoàn hảo không tự đến — nó được xây từng giấy tờ, từng dòng SOP một.' },
  { text: 'Hôm nay bạn chuẩn bị kỹ hơn một chút, ngày mai bạn tự tin hơn rất nhiều.' },
  { text: 'Thất bại một lần không phải kết thúc — đó là bài học để hồ sơ lần sau mạnh hơn.' },
  { text: 'Đừng so sánh chương 1 của bạn với chương 20 của người khác.' },
  { text: 'Mỗi câu trả lời phỏng vấn luyện tập hôm nay là một bước gần hơn tới offer thật.' },
  { text: 'Giấc mơ du học lớn — nhưng bạn đủ nhỏ bé để bắt đầu ngay hôm nay.' },
  { text: 'Khi mệt, hãy nhớ vì sao bạn bắt đầu con đường này.' },
  { text: 'Bạn không cần hoàn hảo — bạn cần chân thành và không bỏ cuộc.' },
  { text: 'Nỗ lực im lặng hôm nay sẽ thành tiếng vỗ tay ngày mai.' },
  { text: 'Một hồ sơ trọn vẹn là lời cam kết: tôi xứng đáng với cơ hội này.' },
  { text: 'Càng chuẩn bị kỹ, phỏng vấn càng trơn tru — Du học Trung Quốc không phải may mắn, là luyện tập.' },
  { text: 'Học bổng không chọn người giỏi nhất — mà chọn người đã cố gắng nhất.' },
  { text: 'Mỗi ngày làm thêm một việc nhỏ, cả hành trình apply sẽ khác hẳn.' },
  { text: 'Điểm số quan trọng, nhưng câu chuyện của bạn mới là thứ khiến hội đồng nhớ mãi.' },
  { text: 'Đừng sợ bắt đầu muộn — hãy sợ dừng lại quá sớm.' },
  { text: 'Mentor tin bạn — hãy tin chính mình nhiều hơn một chút nữa.' },
  { text: 'Giấy tờ đầy đủ, tâm thế vững vàng — bạn đã sẵn sàng hơn bạn nghĩ.' },
  { text: 'Áp lực apply là tạm thời; bản lĩnh bạn rèn trong lúc này là mãi mãi.' },
  { text: 'Hôm nay bạn nộp thêm một mục, ngày mai bạn nhẹ lòng thêm một phần.' },
  { text: 'Du học không chỉ là đi xa — là trở thành phiên bản mạnh mẽ hơn của chính mình.' },
  { text: 'Càng cố gắng, bạn càng xứng đáng với cánh cửa mình sắp gõ.' },
  { text: 'Một câu SOP chân thành mạnh hơn trăm câu sáo rỗng.' },
  { text: 'Bạn đang xây tương lai — hãy kiên nhẫn với quá trình.' },
  { text: 'Mỗi lần sửa hồ sơ là một lần bạn tiến gần hơn tới giấc mơ.' },
  { text: 'Đừng để một lần trượt làm lu mờ hàng trăm ngày bạn đã cố gắng.' },
  { text: 'Hôm nay luyện phỏng vấn, mai bạn tự tin trả lời trước hội đồng thật.' },
  { text: 'Thành công là tổng của những nỗ lực nhỏ lặp lại ngày qua ngày.' },
  { text: 'Bạn đủ giỏi để thử — và đủ mạnh để thử lại nếu cần.' },
  { text: 'Học bổng là phần thưởng — nhưng con người bạn trưởng thành mới là quà lớn nhất.' },
  { text: 'Càng chuẩn bị sớm, càng ít vội vàng — hồ sơ càng sáng.' },
  { text: 'Tin vào quá trình: mỗi bước nhỏ đều có ý nghĩa.' },
  { text: 'Hôm nay bạn làm việc trong im lặng — ngày mai thành quả sẽ lên tiếng.' },
  { text: 'Đường apply dài, nhưng bạn không đi một mình — Du học Trung Quốc đi cùng bạn.' },
  { text: 'Một ngày tốt bắt đầu từ việc hoàn thành một việc nhỏ cho hồ sơ.' },
  { text: 'Đam mê + kỷ luật = hồ sơ đáng được chọn.' },
  { text: 'Bạn sinh ra không phải để dễ dàng — bạn sinh ra để vươn xa.' },
  { text: 'Mỗi cơ hội bị từ chối dạy bạn cách nộp hồ sơ tốt hơn lần sau.' },
  { text: 'Hãy tự hào vì đã dám mơ lớn và dám theo đuổi.' },
];

export function pickRandomQuote() {
  const index = Math.floor(Math.random() * MOTIVATIONAL_QUOTES.length);
  return MOTIVATIONAL_QUOTES[index];
}
