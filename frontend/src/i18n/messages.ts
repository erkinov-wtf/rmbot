export type AppLanguage = "en" | "ru" | "uz";

export type TranslationParams = Record<string, string | number>;

type TranslationCatalog = Record<string, string>;
type TranslationCatalogs = Record<AppLanguage, TranslationCatalog>;

const RU_MESSAGES: TranslationCatalog = {
  "Access not approved yet": "Доступ пока не одобрен",
  "Access not registered": "Доступ не зарегистрирован",
  "Access request under review": "Запрос доступа на рассмотрении",
  "Authentication is handled through Telegram mini app init data.":
    "Аутентификация выполняется через init data Telegram mini app.",
  "Authenticating with Telegram...": "Аутентификация через Telegram...",
  "Assigned": "Назначен",
  "Assign technician": "Назначить техника",
  "Assign Technician": "Назначить техника",
  "Ask admin to approve and link your access request.":
    "Попросите администратора одобрить и привязать ваш запрос доступа.",
  Attendance: "Посещаемость",
  "Attendance days": "Дни посещаемости",
  "Attendance consistency": "Стабильность посещаемости",
  "Attendance contribution": "Вклад посещаемости",
  "Avg duration": "Средняя длительность",
  "Avg work/day": "Средняя работа в день",
  "Back To Leaderboard": "Назад к рейтингу",
  Comment: "Комментарий",
  "Completed days": "Завершенные дни",
  Create: "Создать",
  "Create Ticket": "Создать тикет",
  "Creating ticket...": "Создание тикета...",
  "Could not approve ticket.": "Не удалось одобрить тикет.",
  "Could not assign ticket.": "Не удалось назначить тикет.",
  "Could not authenticate Telegram mini app session.":
    "Не удалось аутентифицировать Telegram mini app сессию.",
  "Could not create ticket.": "Не удалось создать тикет.",
  "Could not load inventory items.": "Не удалось загрузить элементы инвентаря.",
  "Could not load parts.": "Не удалось загрузить части.",
  "Could not load public technician leaderboard.":
    "Не удалось загрузить публичный рейтинг техников.",
  "Could not load QC queue.": "Не удалось загрузить очередь QC.",
  "Could not load review tickets.": "Не удалось загрузить тикеты для проверки.",
  "Could not load technician detail.":
    "Не удалось загрузить детали по технику.",
  "Could not load technician list.":
    "Не удалось загрузить список техников.",
  "Could not process QC action.": "Не удалось выполнить действие QC.",
  "Could not update manual metrics.":
    "Не удалось обновить ручные метрики.",
  "Date range": "Диапазон дат",
  Done: "Готово",
  "Done tickets": "Завершенные тикеты",
  "Enter your username and password.":
    "Введите имя пользователя и пароль.",
  "Each selected part needs a valid minutes value (> 0).":
    "Для каждой выбранной части нужно корректное значение минут (> 0).",
  "Fast login and persistent session": "Быстрый вход и постоянная сессия",
  "Failed To Render {{title}}": "Не удалось отрисовать {{title}}",
  "First Pass": "Первый проход",
  "First-pass completions": "Завершения с первого прохода",
  "First-pass bonus": "Бонус первого прохода",
  "First pass rate": "Доля первого прохода",
  "Flag quality impact": "Влияние качества флагов",
  "Flag quality": "Качество флагов",
  "Flag color": "Цвет флага",
  "Green": "Зеленый",
  "Help menu": "Меню помощи",
  "Hi {{name}}": "Привет, {{name}}",
  "In progress": "В работе",
  Inventory: "Инвентарь",
  "Item #{{id}}": "Элемент #{{id}}",
  "Language": "Язык",
  "Level Control": "Контроль уровня",
  "Level {{level}}": "Уровень {{level}}",
  "Loading items...": "Загрузка элементов...",
  "Loading leaderboard...": "Загрузка рейтинга...",
  "Loading parts...": "Загрузка частей...",
  "Loading QC queue...": "Загрузка очереди QC...",
  "Loading technician details...": "Загрузка данных техника...",
  "Loading technicians...": "Загрузка техников...",
  "Loading tickets...": "Загрузка тикетов...",
  Login: "Вход",
  Logout: "Выйти",
  "Manual metrics": "Ручные метрики",
  "Manual metrics updated for ticket #{{id}}.":
    "Ручные метрики обновлены для тикета #{{id}}.",
  "Minutes": "Минуты",
  "My Profile": "Мой профиль",
  "Mini App": "Мини-приложение",
  "Mini App User": "Пользователь мини-приложения",
  "Mobile flow for ticket create, review, and QC actions.":
    "Мобильный поток для создания, проверки и QC тикетов.",
  "New": "Новый",
  "No matching inventory items.": "Подходящие элементы инвентаря не найдены.",
  "No part specs.": "Нет параметров частей.",
  "No parts are configured for this item category.":
    "Для категории этого элемента части не настроены.",
  "No roles": "Нет ролей",
  "No ticket permissions": "Нет прав на тикеты",
  "No tickets found.": "Тикеты не найдены.",
  "No tickets in QC queue.": "В очереди QC нет тикетов.",
  "No technicians available in leaderboard.":
    "В рейтинге нет доступных техников.",
  "No XP transactions yet.": "Транзакций XP пока нет.",
  "Open this page from Telegram bot mini app button.":
    "Откройте эту страницу кнопкой mini app из Telegram-бота.",
  "Open this page from Telegram bot using the mini app button.":
    "Откройте эту страницу из Telegram-бота через кнопку mini app.",
  "Operations workspace": "Операционное рабочее пространство",
  "Part specs": "Параметры частей",
  Parts: "Части",
  "Penalty": "Штраф",
  "Preparing authentication...": "Подготовка аутентификации...",
  "Preparing mini app...": "Подготовка мини-приложения...",
  "Public Stats": "Публичная статистика",
  "QC": "QC",
  "QC Fail": "QC не пройден",
  "QC failed for ticket #{{id}}.": "QC не пройден для тикета #{{id}}.",
  "QC Pass": "QC пройден",
  "QC passed for ticket #{{id}}.": "QC пройден для тикета #{{id}}.",
  "QC queue": "Очередь QC",
  "Quality flags": "Флаги качества",
  Refresh: "Обновить",
  "Recheck Access": "Проверить доступ снова",
  "Reopen mini app from bot.": "Переоткройте mini app из бота.",
  "Reload this page. If the issue continues, contact support.":
    "Перезагрузите страницу. Если проблема повторится, обратитесь в поддержку.",
  "Rent Market": "Rent Market",
  Rework: "Доработка",
  Review: "Проверка",
  "Review queue": "Очередь проверки",
  Rules: "Правила",
  "Rules Panel": "Панель правил",
  "Save Manual Metrics": "Сохранить ручные метрики",
  "Score": "Счет",
  "Search by serial or name": "Поиск по серийному номеру или названию",
  "Search ticket id, serial, title":
    "Поиск по ID тикета, серийному номеру, названию",
  "Secure access": "Защищенный доступ",
  "Select a QC ticket to continue.":
    "Выберите тикет QC, чтобы продолжить.",
  "Select a review ticket to continue.":
    "Выберите тикет для проверки, чтобы продолжить.",
  "Select a technician to assign.": "Выберите техника для назначения.",
  "Select an inventory item first.": "Сначала выберите элемент инвентаря.",
  "Select an item to create a new repair ticket.":
    "Выберите элемент для создания нового ремонтного тикета.",
  "Select at least one part for the ticket.":
    "Выберите хотя бы одну часть для тикета.",
  "Select technician": "Выберите техника",
  "Selected": "Выбрано",
  "Session cleared. Reopen mini app from Telegram.":
    "Сессия очищена. Откройте mini app из Telegram заново.",
  "Session expired or invalid. Please log in again.":
    "Сессия истекла или недействительна. Войдите снова.",
  "Session expired. Please log in again.":
    "Сессия истекла. Войдите снова.",
  "Session expired. Reopen mini app from Telegram.":
    "Сессия истекла. Откройте mini app из Telegram заново.",
  "Session is stored in localStorage and expires automatically when JWT `exp` is reached.":
    "Сессия хранится в localStorage и истекает автоматически при достижении JWT `exp`.",
  "Sign In": "Войти",
  "Sign in with your backend account to continue.":
    "Войдите с вашим backend-аккаунтом, чтобы продолжить.",
  "Signing in...": "Вход...",
  "Status Counts (All Time)": "Счетчики статусов (за все время)",
  "System score": "Системный счет",
  "Technician": "Техник",
  "Technician Top Chart": "Топ-рейтинг техников",
  "Telegram account is not linked to an active user.":
    "Ваш Telegram-аккаунт не привязан к активному пользователю.",
  "Telegram ID: {{id}}": "Telegram ID: {{id}}",
  "Telegram initData is missing. Reopen mini app from bot.":
    "Отсутствует Telegram initData. Переоткройте mini app из бота.",
  "Telegram Mini App": "Telegram Mini App",
  "Ticket #{{id}}": "Тикет #{{id}}",
  "Ticket #{{id}} approved.": "Тикет #{{id}} одобрен.",
  "Ticket #{{id}} assigned.": "Тикет #{{id}} назначен.",
  "Ticket Flow": "Поток тикетов",
  "Ticket created successfully.": "Тикет успешно создан.",
  "Ticket Workspace": "Рабочая зона тикетов",
  "Ticket title (optional)": "Название тикета (необязательно)",
  Tickets: "Тикеты",
  "To continue": "Чтобы продолжить",
  "Top {{value}}%": "Топ {{value}}%",
  "Top Positive Factors": "Главные положительные факторы",
  "Top Negative Factors": "Главные отрицательные факторы",
  "Total XP": "Всего XP",
  "Under review": "На проверке",
  Users: "Пользователи",
  "Username: @{{username}}": "Имя пользователя: @{{username}}",
  "Waiting QC": "Ожидает QC",
  "Why This Rank": "Почему этот ранг",
  "XP Breakdown": "Разбор XP",
  "XP Control": "Управление XP",
  "XP amount": "Количество XP",
  "XP amount must be 0 or higher.": "Количество XP должно быть 0 или больше.",
  "Yellow": "Желтый",
  "1st pass": "1-й проход",
  "API endpoint": "API endpoint",
  "All": "Все",
  "Amount": "Сумма",
  "Approve Review": "Одобрить проверку",
  "Attend": "Посещ.",
  "Authenticated User": "Аутентифицированный пользователь",
  "Automatic logout on token expiry": "Автоматический выход при истечении токена",
  "Cannot reach backend. Check CORS and backend availability.":
    "Не удается подключиться к backend. Проверьте CORS и доступность backend.",
  "Choose an inventory item to start ticket creation.":
    "Выберите элемент инвентаря, чтобы начать создание тикета.",
  "Closed Tickets": "Закрытые тикеты",
  "Closed flags": "Закрытые флаги",
  "Closed tickets contribution": "Вклад закрытых тикетов",
  "Duration": "Длительность",
  "Entries": "Записи",
  "Failed To Render": "Не удалось отрисовать",
  "Failed to load current user profile.":
    "Не удалось загрузить профиль текущего пользователя.",
  "First Pass Rate": "Доля первого прохода",
  "First pass": "Первый проход",
  "Login failed with an unknown error.": "Ошибка входа с неизвестной причиной.",
  "No done tickets yet.": "Пока нет завершенных тикетов.",
  "No negative factors.": "Нет отрицательных факторов.",
  "No positive factors.": "Нет положительных факторов.",
  "Password": "Пароль",
  "QC fail events": "События QC fail",
  "QC pass events": "События QC pass",
  "Rank": "Ранг",
  "Recent Done Tickets": "Недавние завершенные тикеты",
  "Recent XP Activity": "Недавняя активность XP",
  "Red": "Красный",
  "Ref": "Ссылка",
  "Tasks": "Задачи",
  "Technicians": "Техники",
  "Ticket Quality": "Качество тикетов",
  "Unknown rendering error.": "Неизвестная ошибка рендеринга.",
  "Username": "Имя пользователя",
  "You do not have permission to approve review.":
    "У вас нет прав на одобрение проверки.",
  "You do not have permission to run QC actions.":
    "У вас нет прав на выполнение QC действий.",
  "Your account does not have create/review/qc access.":
    "У вашей учетной записи нет доступа к create/review/qc.",
  "your.username": "ваш.username",
};

const UZ_MESSAGES: TranslationCatalog = {
  "Access not approved yet": "Kirish hali tasdiqlanmagan",
  "Access not registered": "Kirish ro'yxatdan o'tmagan",
  "Access request under review": "Kirish so'rovi ko'rib chiqilmoqda",
  "Authentication is handled through Telegram mini app init data.":
    "Autentifikatsiya Telegram mini app init data orqali amalga oshiriladi.",
  "Authenticating with Telegram...": "Telegram orqali autentifikatsiya qilinmoqda...",
  "Assigned": "Biriktirilgan",
  "Assign technician": "Texnikni biriktirish",
  "Assign Technician": "Texnikni biriktirish",
  "Ask admin to approve and link your access request.":
    "Admin'dan kirish so'rovingizni tasdiqlab bog'lashni so'rang.",
  Attendance: "Davomat",
  "Attendance days": "Davomat kunlari",
  "Attendance consistency": "Davomat barqarorligi",
  "Attendance contribution": "Davomat hissasi",
  "Avg duration": "O'rtacha davomiylik",
  "Avg work/day": "Kunlik o'rtacha ish",
  "Back To Leaderboard": "Reytingga qaytish",
  Comment: "Izoh",
  "Completed days": "Yakunlangan kunlar",
  Create: "Yaratish",
  "Create Ticket": "Ariza yaratish",
  "Creating ticket...": "Ariza yaratilmoqda...",
  "Could not approve ticket.": "Arizani tasdiqlab bo'lmadi.",
  "Could not assign ticket.": "Arizani biriktirib bo'lmadi.",
  "Could not authenticate Telegram mini app session.":
    "Telegram mini app sessiyasini autentifikatsiya qilib bo'lmadi.",
  "Could not create ticket.": "Ariza yaratib bo'lmadi.",
  "Could not load inventory items.":
    "Inventar elementlarini yuklab bo'lmadi.",
  "Could not load parts.": "Qismlarni yuklab bo'lmadi.",
  "Could not load public technician leaderboard.":
    "Ommaviy texniklar reytingini yuklab bo'lmadi.",
  "Could not load QC queue.": "QC navbatini yuklab bo'lmadi.",
  "Could not load review tickets.": "Ko'rib chiqish arizalarini yuklab bo'lmadi.",
  "Could not load technician detail.": "Texnik tafsilotlarini yuklab bo'lmadi.",
  "Could not load technician list.": "Texniklar ro'yxatini yuklab bo'lmadi.",
  "Could not process QC action.": "QC amalini bajarib bo'lmadi.",
  "Could not update manual metrics.": "Qo'lda metrikalarni yangilab bo'lmadi.",
  "Date range": "Sana oralig'i",
  Done: "Yakunlangan",
  "Done tickets": "Yakunlangan arizalar",
  "Enter your username and password.":
    "Foydalanuvchi nomi va parolingizni kiriting.",
  "Each selected part needs a valid minutes value (> 0).":
    "Har bir tanlangan qism uchun to'g'ri daqiqa qiymati kerak (> 0).",
  "Fast login and persistent session":
    "Tez kirish va saqlanadigan sessiya",
  "Failed To Render {{title}}": "{{title}} ni render qilib bo'lmadi",
  "First Pass": "Birinchi urinish",
  "First-pass completions": "Birinchi urinishda yakunlash",
  "First-pass bonus": "Birinchi urinish bonusi",
  "First pass rate": "Birinchi urinish foizi",
  "Flag quality impact": "Flag sifati ta'siri",
  "Flag quality": "Flag sifati",
  "Flag color": "Flag rangi",
  Green: "Yashil",
  "Help menu": "Yordam menyusi",
  "Hi {{name}}": "Salom, {{name}}",
  "In progress": "Jarayonda",
  Inventory: "Inventar",
  "Item #{{id}}": "Element #{{id}}",
  Language: "Til",
  "Level Control": "Daraja nazorati",
  "Level {{level}}": "{{level}}-daraja",
  "Loading items...": "Elementlar yuklanmoqda...",
  "Loading leaderboard...": "Reyting yuklanmoqda...",
  "Loading parts...": "Qismlar yuklanmoqda...",
  "Loading QC queue...": "QC navbati yuklanmoqda...",
  "Loading technician details...": "Texnik tafsilotlari yuklanmoqda...",
  "Loading technicians...": "Texniklar yuklanmoqda...",
  "Loading tickets...": "Arizalar yuklanmoqda...",
  Login: "Kirish",
  Logout: "Chiqish",
  "Manual metrics": "Qo'lda metrikalar",
  "Manual metrics updated for ticket #{{id}}.":
    "#{{id}} ariza uchun qo'lda metrikalar yangilandi.",
  Minutes: "Daqiqa",
  "My Profile": "Mening profilim",
  "Mini App": "Mini App",
  "Mini App User": "Mini App foydalanuvchisi",
  "Mobile flow for ticket create, review, and QC actions.":
    "Ariza yaratish, ko'rib chiqish va QC amallari uchun mobil oqim.",
  New: "Yangi",
  "No matching inventory items.": "Mos inventar elementlari topilmadi.",
  "No part specs.": "Qism parametrlari yo'q.",
  "No parts are configured for this item category.":
    "Ushbu element kategoriyasi uchun qismlar sozlanmagan.",
  "No roles": "Rollar yo'q",
  "No ticket permissions": "Ariza ruxsatlari yo'q",
  "No tickets found.": "Arizalar topilmadi.",
  "No tickets in QC queue.": "QC navbatida arizalar yo'q.",
  "No technicians available in leaderboard.":
    "Reytingda texniklar mavjud emas.",
  "No XP transactions yet.": "Hali XP tranzaksiyalari yo'q.",
  "Open this page from Telegram bot mini app button.":
    "Ushbu sahifani Telegram botidagi mini app tugmasi orqali oching.",
  "Open this page from Telegram bot using the mini app button.":
    "Ushbu sahifani Telegram botidagi mini app tugmasi orqali oching.",
  "Operations workspace": "Operatsion ish maydoni",
  "Part specs": "Qism parametrlari",
  Parts: "Qismlar",
  Penalty: "Jarima",
  "Preparing authentication...": "Autentifikatsiya tayyorlanmoqda...",
  "Preparing mini app...": "Mini app tayyorlanmoqda...",
  "Public Stats": "Ommaviy statistika",
  QC: "QC",
  "QC Fail": "QC muvaffaqiyatsiz",
  "QC failed for ticket #{{id}}.": "#{{id}} ariza uchun QC muvaffaqiyatsiz.",
  "QC Pass": "QC muvaffaqiyatli",
  "QC passed for ticket #{{id}}.": "#{{id}} ariza uchun QC muvaffaqiyatli.",
  "QC queue": "QC navbati",
  "Quality flags": "Sifat flaglari",
  Refresh: "Yangilash",
  "Recheck Access": "Kirishni qayta tekshirish",
  "Reopen mini app from bot.": "Mini app'ni botdan qayta oching.",
  "Reload this page. If the issue continues, contact support.":
    "Sahifani qayta yuklang. Muammo davom etsa, qo'llab-quvvatlashga murojaat qiling.",
  "Rent Market": "Rent Market",
  Rework: "Qayta ishlash",
  Review: "Ko'rib chiqish",
  "Review queue": "Ko'rib chiqish navbati",
  Rules: "Qoidalar",
  "Rules Panel": "Qoidalar paneli",
  "Save Manual Metrics": "Qo'lda metrikalarni saqlash",
  Score: "Ball",
  "Search by serial or name": "Seriya raqami yoki nom bo'yicha qidirish",
  "Search ticket id, serial, title":
    "Ariza ID, seriya raqami, nom bo'yicha qidirish",
  "Secure access": "Xavfsiz kirish",
  "Select a QC ticket to continue.":
    "Davom etish uchun QC arizasini tanlang.",
  "Select a review ticket to continue.":
    "Davom etish uchun ko'rib chiqish arizasini tanlang.",
  "Select a technician to assign.": "Biriktirish uchun texnikni tanlang.",
  "Select an inventory item first.": "Avval inventar elementini tanlang.",
  "Select an item to create a new repair ticket.":
    "Yangi ta'mirlash arizasini yaratish uchun elementni tanlang.",
  "Select at least one part for the ticket.":
    "Ariza uchun kamida bitta qismni tanlang.",
  "Select technician": "Texnikni tanlang",
  Selected: "Tanlangan",
  "Session cleared. Reopen mini app from Telegram.":
    "Sessiya tozalandi. Mini app'ni Telegramdan qayta oching.",
  "Session expired or invalid. Please log in again.":
    "Sessiya tugagan yoki noto'g'ri. Qayta kiring.",
  "Session expired. Please log in again.":
    "Sessiya tugadi. Qayta kiring.",
  "Session expired. Reopen mini app from Telegram.":
    "Sessiya tugadi. Mini app'ni Telegramdan qayta oching.",
  "Session is stored in localStorage and expires automatically when JWT `exp` is reached.":
    "Sessiya localStorage'da saqlanadi va JWT `exp` ga yetganda avtomatik tugaydi.",
  "Sign In": "Kirish",
  "Sign in with your backend account to continue.":
    "Davom etish uchun backend hisobingiz bilan kiring.",
  "Signing in...": "Kirilmoqda...",
  "Status Counts (All Time)": "Holatlar soni (hamma vaqt)",
  "System score": "Tizim balli",
  Technician: "Texnik",
  "Technician Top Chart": "Texniklar top reytingi",
  "Telegram account is not linked to an active user.":
    "Telegram hisobingiz faol foydalanuvchiga bog'lanmagan.",
  "Telegram ID: {{id}}": "Telegram ID: {{id}}",
  "Telegram initData is missing. Reopen mini app from bot.":
    "Telegram initData mavjud emas. Mini app'ni botdan qayta oching.",
  "Telegram Mini App": "Telegram Mini App",
  "Ticket #{{id}}": "Ariza #{{id}}",
  "Ticket #{{id}} approved.": "Ariza #{{id}} tasdiqlandi.",
  "Ticket #{{id}} assigned.": "Ariza #{{id}} biriktirildi.",
  "Ticket Flow": "Ariza oqimi",
  "Ticket created successfully.": "Ariza muvaffaqiyatli yaratildi.",
  "Ticket Workspace": "Ariza ish maydoni",
  "Ticket title (optional)": "Ariza nomi (ixtiyoriy)",
  Tickets: "Arizalar",
  "To continue": "Davom etish uchun",
  "Top {{value}}%": "Top {{value}}%",
  "Top Positive Factors": "Asosiy ijobiy omillar",
  "Top Negative Factors": "Asosiy salbiy omillar",
  "Total XP": "Jami XP",
  "Under review": "Ko'rib chiqilmoqda",
  Users: "Foydalanuvchilar",
  "Username: @{{username}}": "Foydalanuvchi nomi: @{{username}}",
  "Waiting QC": "QC kutilmoqda",
  "Why This Rank": "Nega bu o'rin",
  "XP Breakdown": "XP taqsimoti",
  "XP Control": "XP nazorati",
  "XP amount": "XP miqdori",
  "XP amount must be 0 or higher.": "XP miqdori 0 yoki undan katta bo'lishi kerak.",
  Yellow: "Sariq",
  "1st pass": "1-urinish",
  "API endpoint": "API manzili",
  "All": "Barchasi",
  "Amount": "Miqdor",
  "Approve Review": "Ko'rib chiqishni tasdiqlash",
  "Attend": "Dav.",
  "Authenticated User": "Autentifikatsiyalangan foydalanuvchi",
  "Automatic logout on token expiry":
    "Token muddati tugaganda avtomatik chiqish",
  "Cannot reach backend. Check CORS and backend availability.":
    "Backend bilan bog'lanib bo'lmadi. CORS va backend holatini tekshiring.",
  "Choose an inventory item to start ticket creation.":
    "Ariza yaratishni boshlash uchun inventar elementini tanlang.",
  "Closed Tickets": "Yopilgan arizalar",
  "Closed flags": "Yopilgan flaglar",
  "Closed tickets contribution": "Yopilgan arizalar hissasi",
  "Duration": "Davomiylik",
  "Entries": "Yozuvlar",
  "Failed To Render": "Render qilib bo'lmadi",
  "Failed to load current user profile.":
    "Joriy foydalanuvchi profilini yuklab bo'lmadi.",
  "First Pass Rate": "Birinchi urinish foizi",
  "First pass": "Birinchi urinish",
  "Login failed with an unknown error.":
    "Kirish noma'lum xatolik bilan muvaffaqiyatsiz tugadi.",
  "No done tickets yet.": "Hali yakunlangan arizalar yo'q.",
  "No negative factors.": "Salbiy omillar yo'q.",
  "No positive factors.": "Ijobiy omillar yo'q.",
  "Password": "Parol",
  "QC fail events": "QC fail hodisalari",
  "QC pass events": "QC pass hodisalari",
  "Rank": "O'rin",
  "Recent Done Tickets": "So'nggi yakunlangan arizalar",
  "Recent XP Activity": "So'nggi XP faolligi",
  "Red": "Qizil",
  "Ref": "Havola",
  "Tasks": "Vazifalar",
  "Technicians": "Texniklar",
  "Ticket Quality": "Ariza sifati",
  "Unknown rendering error.": "Noma'lum render xatosi.",
  "Username": "Foydalanuvchi nomi",
  "You do not have permission to approve review.":
    "Ko'rib chiqishni tasdiqlash uchun sizda ruxsat yo'q.",
  "You do not have permission to run QC actions.":
    "QC amallarini bajarish uchun sizda ruxsat yo'q.",
  "Your account does not have create/review/qc access.":
    "Hisobingizda create/review/qc kirish huquqi yo'q.",
  "your.username": "sizning.username",
};

const EN_MESSAGES: TranslationCatalog = {};

const MESSAGES: TranslationCatalogs = {
  en: EN_MESSAGES,
  ru: RU_MESSAGES,
  uz: UZ_MESSAGES,
};

function applyParams(
  template: string,
  params: TranslationParams | undefined,
): string {
  if (!params) {
    return template;
  }
  return template.replace(/\{\{(\w+)\}\}/g, (full, key: string) => {
    if (!(key in params)) {
      return full;
    }
    return String(params[key]);
  });
}

export function translateMessage(
  key: string,
  language: AppLanguage,
  params?: TranslationParams,
): string {
  const catalog = MESSAGES[language];
  const translated = catalog[key] ?? key;
  return applyParams(translated, params);
}
