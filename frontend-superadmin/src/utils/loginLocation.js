export const LOCATION_REQUIRED_MESSAGE =
  'Vì mục đích an toàn và đảm bảo quyền lợi cho mentee Du học Trung Quốc, bạn vui lòng đồng ý cấp quyền vị trí. Du học Trung Quốc chỉ sử dụng thông tin này nội bộ và không mang mục đích doanh nghiệp.';

function geolocationErrorMessage(error) {
  if (!error) return LOCATION_REQUIRED_MESSAGE;
  if (error.code === 1) {
    return (
      'Trình duyệt đang chặn vị trí. Bấm "Cho phép truy cập vị trí" và chọn Allow/Cho phép. ' +
      'Nếu không thấy hộp thoại: Cài đặt trình duyệt → Quyền riêng tư → Vị trí → bật cho trang này.'
    );
  }
  if (error.code === 2) {
    return 'Không lấy được vị trí. Hãy bật GPS / Dịch vụ vị trí trên điện thoại rồi thử lại.';
  }
  if (error.code === 3) {
    return 'Hết thời gian chờ vị trí. Hãy bật GPS, ra ngoài trời hoặc thử lại.';
  }
  return LOCATION_REQUIRED_MESSAGE;
}

function readPosition(position) {
  return {
    location_granted: true,
    latitude: position.coords.latitude,
    longitude: position.coords.longitude,
    accuracy: position.coords.accuracy,
  };
}

export function locationPermissionSupported() {
  return typeof window !== 'undefined' && window.isSecureContext && !!navigator.geolocation;
}

export function requestLoginLocation() {
  return new Promise((resolve, reject) => {
    if (typeof window === 'undefined') {
      reject(new Error(LOCATION_REQUIRED_MESSAGE));
      return;
    }

    if (!window.isSecureContext) {
      reject(
        new Error(
          'Cần mở link bằng HTTPS (link trycloudflare hoặc domain bảo mật) mới cấp quyền vị trí được.',
        ),
      );
      return;
    }

    if (!navigator.geolocation) {
      reject(new Error(LOCATION_REQUIRED_MESSAGE));
      return;
    }

    const options = { enableHighAccuracy: false, timeout: 45000, maximumAge: 0 };

    navigator.geolocation.getCurrentPosition(
      (position) => resolve(readPosition(position)),
      (error) => {
        if (error.code === 3) {
          navigator.geolocation.getCurrentPosition(
            (position) => resolve(readPosition(position)),
            (retryError) => reject(new Error(geolocationErrorMessage(retryError))),
            { enableHighAccuracy: true, timeout: 60000, maximumAge: 0 },
          );
          return;
        }
        reject(new Error(geolocationErrorMessage(error)));
      },
      options,
    );
  });
}
