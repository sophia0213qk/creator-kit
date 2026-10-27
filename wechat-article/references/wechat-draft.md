# 上传草稿箱 API 速查

官方文档：

- [获取 access_token](https://developers.weixin.qq.com/doc/subscription/api/base/api_getaccesstoken.html)
- [上传永久素材（封面）](https://developers.weixin.qq.com/doc/subscription/api/material/permanent/api_addmaterial.html)
- [上传发表内容中的图片（正文）](https://developers.weixin.qq.com/doc/subscription/api/material/permanent/api_uploadimage.html)
- [新增草稿](https://developers.weixin.qq.com/doc/subscription/api/draftbox/draftmanage/api_draft_add.html)（接口路径 `/cgi-bin/draft/add`）
- [获取草稿详情](https://developers.weixin.qq.com/doc/subscription/api/draftbox/draftmanage/api_getdraft.html)
- [服务端调用与 IP 白名单说明](https://developers.weixin.qq.com/doc/subscription/guide/dev/api/)

## 本地入口

```bash
# 只有 md + images/ 时也会先 md_to_html，再上传
python scripts/upload_draft.py "成稿目录"
python scripts/upload_draft.py "成稿目录/文章.md"
```

正文图上传后，脚本会把 HTML 内本地 `src` 替换为微信 `url`，再 `draft/add`；同时写出 `文章名.wx.html`。

## 凭证

```
GET https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid=APPID&secret=SECRET
```

调用 IP 必须在公众号「开发密钥 → IP 白名单」内，否则 `40164`。

## 封面

```
POST https://api.weixin.qq.com/cgi-bin/material/add_material?access_token=TOKEN&type=image
form-data: media=@cover.jpg
```

返回 `media_id`（永久）→ 草稿字段 `thumb_media_id`。

## 正文图

```
POST https://api.weixin.qq.com/cgi-bin/media/uploadimg?access_token=TOKEN
form-data: media=@inline.jpg
```

返回 `url`。仅 jpg/png，且 **< 1MB**。外部图片链接会被过滤。

## 新增草稿

```
POST https://api.weixin.qq.com/cgi-bin/draft/add?access_token=TOKEN
```

```json
{
  "articles": [{
    "article_type": "news",
    "title": "不超过32字",
    "author": "",
    "digest": "不超过120字",
    "content": "<p>HTML，正文图必须是 uploadimg 返回的 url</p>",
    "thumb_media_id": "封面永久素材 media_id",
    "need_open_comment": 0,
    "only_fans_can_comment": 0
  }]
}
```

`author` 固定传空：页面顶部已显示公众号名称，再填会叠成双作者。

返回 `media_id`。

## 校验

```
POST https://api.weixin.qq.com/cgi-bin/draft/get?access_token=TOKEN
{"media_id":"..."}
```

核对 `news_item[0].title` 与本地标题一致，视为上传成功。
