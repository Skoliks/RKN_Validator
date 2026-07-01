from app.analyzers.owner_requisites_analyzer import OwnerRequisitesAnalyzer
from app.schemas.pages import PageData


def make_page(html: str, url: str = "https://example.ru") -> PageData:
    return PageData(url=url, final_url=url, status_code=200, html=html)


def test_owner_requisites_analyzer_detects_company_inn_and_ogrn() -> None:
    page = make_page('<p>ООО "ИнфоКом"</p><p>ИНН: 2801121089</p><p>ОГРН 1072801006530</p>')

    result = OwnerRequisitesAnalyzer().analyze([page])

    assert result.found is True
    assert result.organization_name == 'ООО "ИнфоКом"'
    assert result.inn == "2801121089"
    assert result.ogrn == "1072801006530"


def test_owner_requisites_analyzer_detects_ip_and_ogrnip() -> None:
    page = make_page(
        "<p>Индивидуальный предприниматель Иванов Иван Иванович</p>"
        "<p>ОГРНИП 304500116000157</p>"
    )

    result = OwnerRequisitesAnalyzer().analyze([page])

    assert result.found is True
    assert result.person_name == "Индивидуальный предприниматель Иванов Иван Иванович"
    assert result.ogrnip == "304500116000157"


def test_owner_requisites_analyzer_detects_russian_phone() -> None:
    page = make_page("<p>Телефон: +7 (495) 123-45-67</p>")

    result = OwnerRequisitesAnalyzer().analyze([page])

    assert result.found is True
    assert result.phone_found is True


def test_owner_requisites_analyzer_detects_regular_email() -> None:
    page = make_page("<p>Email: info@example.ru</p>")

    result = OwnerRequisitesAnalyzer().analyze([page])

    assert result.found is True
    assert result.email_found is True
    assert result.privacy_email_found is False


def test_owner_requisites_analyzer_detects_privacy_email() -> None:
    page = make_page("<p>Для запросов: privacy@example.ru</p>")

    result = OwnerRequisitesAnalyzer().analyze([page])

    assert result.found is True
    assert result.email_found is True
    assert result.privacy_email_found is True


def test_owner_requisites_analyzer_returns_empty_result_without_requisites() -> None:
    page = make_page("<p>Добро пожаловать на сайт компании.</p>")

    result = OwnerRequisitesAnalyzer().analyze([page])

    assert result.found is False
    assert result.items == []


def test_owner_requisites_analyzer_does_not_treat_rf_alone_as_address() -> None:
    page = make_page("<p>Работаем на территории РФ.</p>")

    result = OwnerRequisitesAnalyzer().analyze([page])

    assert result.found is False
    assert result.address_found is False
    assert result.warnings == ["Found weak address marker 'РФ' without additional address details."]


def test_owner_requisites_analyzer_extracts_short_legal_address_after_label() -> None:
    page = make_page(
        """
        <footer>
          Юридический адрес: 675000, Амурская область, г. Благовещенск, ул. Ленина, д. 1, офис 5.
          Телефон: +7 (4162) 12-34-56.
          Email: info@example.ru.
          © 2026 ООО "ИнфоКом".
        </footer>
        """
    )

    result = OwnerRequisitesAnalyzer().analyze([page])
    address = next(item for item in result.items if item.field_type == "address")

    assert result.address_found is True
    assert address.value == "675000, Амурская область, г. Благовещенск, ул. Ленина, д. 1, офис 5"
    assert "info@example.ru" not in address.value
    assert "+7" not in address.value
    assert "©" not in address.value


def test_owner_requisites_analyzer_address_fragment_does_not_include_email_phone_or_copyright() -> None:
    page = make_page(
        """
        <p>Контакты: г. Благовещенск, ул. Ленина, д. 1, офис 5; телефон +7 (4162) 12-34-56; email info@example.ru; © 2026</p>
        """
    )

    result = OwnerRequisitesAnalyzer().analyze([page])
    address = next(item for item in result.items if item.field_type == "address")

    assert "г. Благовещенск, ул. Ленина, д. 1, офис 5" in address.value
    assert "info@example.ru" not in address.value
    assert "+7" not in address.value
    assert "©" not in address.value


def test_owner_requisites_analyzer_cuts_address_before_copyright() -> None:
    page = make_page(
        """
        <footer>
          г. Благовещенск, Амурская область © 2019-2024 InfoCom.
          ООО «ИнфоКом» ИНН 2801121089.
        </footer>
        """
    )

    result = OwnerRequisitesAnalyzer().analyze([page])
    address = next(item for item in result.items if item.field_type == "address")

    assert address.value == "г. Благовещенск, Амурская область"
    assert "©" not in address.value


def test_owner_requisites_analyzer_cuts_address_before_inn() -> None:
    page = make_page(
        """
        <footer>
          г. Благовещенск, Амурская область ИНН 2801121089 ОГРН 1072801006530
        </footer>
        """
    )

    result = OwnerRequisitesAnalyzer().analyze([page])
    address = next(item for item in result.items if item.field_type == "address")

    assert address.value == "г. Благовещенск, Амурская область"
    assert "ИНН" not in address.value


def test_owner_requisites_analyzer_cuts_address_before_whatsapp() -> None:
    page = make_page(
        """
        <footer>
          ул. Зейская, 173, офис 403. WhatsApp (только сообщения, звонки не принимаются)
        </footer>
        """
    )

    result = OwnerRequisitesAnalyzer().analyze([page])
    address = next(item for item in result.items if item.field_type == "address")

    assert address.value == "ул. Зейская, 173, офис 403"
    assert "WhatsApp" not in address.value


def test_owner_requisites_analyzer_address_value_does_not_contain_service_markers() -> None:
    page = make_page(
        """
        <footer>
          г. Благовещенск, Амурская область © 2019 InfoCom ИНН 2801121089
          ОГРН 1072801006530 WhatsApp +7 (4162) 12-34-56
        </footer>
        """
    )

    result = OwnerRequisitesAnalyzer().analyze([page])
    address = next(item for item in result.items if item.field_type == "address")

    assert len(address.value) <= 120
    assert "ИНН" not in address.value
    assert "ОГРН" not in address.value
    assert "WhatsApp" not in address.value
    assert "©" not in address.value


def test_owner_requisites_analyzer_extracts_legal_and_postal_addresses_separately() -> None:
    page = make_page(
        """
        <footer>
          Юридический адрес: 675000, Амурская область, г. Благовещенск, ул. Ленина, д. 1.
          Почтовый адрес: 675002, Амурская область, г. Благовещенск, ул. Зейская, 173, офис 403.
          Телефон: +7 (4162) 12-34-56
        </footer>
        """
    )

    result = OwnerRequisitesAnalyzer().analyze([page])
    addresses = [item.value for item in result.items if item.field_type == "address"]

    assert addresses == [
        "675000, Амурская область, г. Благовещенск, ул. Ленина, д. 1",
        "675002, Амурская область, г. Благовещенск, ул. Зейская, 173, офис 403",
    ]


def test_owner_requisites_analyzer_does_not_use_news_organization_as_owner() -> None:
    page = make_page(
        """
        <main>
          <article>
            <h1>Новости партнёров</h1>
            <p>ООО «Газпром переработка Благовещенск» провело мероприятие для студентов.</p>
          </article>
        </main>
        """,
        url="https://amursu.ru/news/partner-event",
    )

    result = OwnerRequisitesAnalyzer().analyze([page])

    assert result.organization_name is None
    assert result.found is False
    assert all("Газпром переработка Благовещенск" not in item.value for item in result.items)


def test_owner_requisites_analyzer_uses_footer_owner_signal() -> None:
    page = make_page(
        """
        <footer>
          © ФГБОУ ВО Амурский государственный университет
        </footer>
        <main>
          <p>ООО «Газпром переработка Благовещенск» упоминается в новости.</p>
        </main>
        """,
        url="https://amursu.ru",
    )

    result = OwnerRequisitesAnalyzer().analyze([page])

    assert result.found is True
    assert result.organization_name == "ФГБОУ ВО Амурский государственный университет"
    assert result.manual_check_required is False


def test_owner_requisites_analyzer_requires_manual_check_for_conflicting_owner_mentions() -> None:
    page = make_page(
        """
        <footer>
          © ООО «Первая организация»
          <div>Реквизиты: ООО «Вторая организация» ИНН 7700000000</div>
        </footer>
        """
    )

    result = OwnerRequisitesAnalyzer().analyze([page])

    assert result.found is True
    assert result.organization_name is None
    assert result.manual_check_required is True
    assert any("разные упоминания организаций" in warning for warning in result.warnings)
